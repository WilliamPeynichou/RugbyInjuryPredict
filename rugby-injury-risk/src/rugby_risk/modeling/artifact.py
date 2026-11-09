"""Local persistence of a fitted M2 (F30): reload it for profile simulations without MCMC.

Stored under `data/models/<run_id>/` (gitignored, never published):

- `draws.npz`: posterior draws of the population-level parameters only. Player and
  team-season effects are NOT stored: a profile is always a new player / team-season, whose
  effects are integrated (Gauss-Hermite, F22).
- `design_frame.parquet`: the feature columns the design transform was learned on (no
  `player_key`, no match/team id, no target). patsy's DesignInfo cannot be pickled (spline
  knots live there), so the transform is rebuilt from this frame on load and checked against
  the stored statistics: any drift raises instead of silently predicting with other knots.
- `meta.json`: provenance (dataset_version, git_sha, seasons), MCMC diagnostics, position
  index and scenario profiles.

Promotion stays human (docs/06 §5): a model is "promoted" only if a human writes
`PROMOTION.md` (decision, date, review report) next to the artifact.
"""

from __future__ import annotations

import json
from dataclasses import asdict
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Final

import numpy as np
import polars as pl

from rugby_risk.features.registry import FORBIDDEN_COLUMNS, ID_COLUMNS
from rugby_risk.modeling.design import FittedTransform, build_design
from rugby_risk.modeling.hierarchical import (
    FIXED_SPEC,
    HierarchicalHazardModel,
    McmcDiagnostics,
    _Index,
    _Posterior,
)

MODELS_DIR: Final = Path("data/models")
PROMOTION_FILE: Final = "PROMOTION.md"
ARTIFACT_VERSION: Final = 1
_STORED_DRAWS: Final = ("alpha", "position_effect", "slope", "beta_load", "beta")
_SIGMAS: Final = ("sigma_player", "sigma_team")
_EMPTY_EFFECTS: Final = ("player_effect", "team_effect")


class ArtifactError(RuntimeError):
    """Artifact missing, inconsistent or not usable (e.g. failed MCMC)."""


def _design_columns() -> list[str]:
    return list(dict.fromkeys([*FIXED_SPEC.source_columns(), FIXED_SPEC.exposure]))


def _transform_summary(t: FittedTransform) -> dict[str, Any]:
    """JSON-comparable statistics of a transform (design_info excluded)."""
    summary: dict[str, Any] = json.loads(
        json.dumps(
            {
                "formula": t.formula,
                "dropped": list(t.dropped),
                "linearised": list(t.linearised),
                "medians": t.medians,
                "bounds": {k: list(v) for k, v in t.bounds.items()},
                "means": t.means,
                "stds": t.stds,
                "levels": {k: list(v) for k, v in t.levels.items()},
            }
        )
    )
    return summary


def design_frame(train: pl.DataFrame) -> pl.DataFrame:
    """Feature columns only: identifiers and targets never reach the artifact."""
    frame = train.select(_design_columns())
    leaked = set(frame.columns) & (set(ID_COLUMNS) | FORBIDDEN_COLUMNS | {FIXED_SPEC.target})
    if leaked:
        raise ArtifactError(f"Colonnes interdites dans l'artefact : {sorted(leaked)}")
    return frame


def save_hierarchical(  # noqa: PLR0913 - provenance complète de l'artefact
    model: HierarchicalHazardModel,
    train: pl.DataFrame,
    *,
    seasons: tuple[str, ...],
    dataset_version: str,
    git_sha: str | None,
    root: Path = MODELS_DIR,
) -> Path:
    """Persist a fitted M2; the rebuilt transform must equal the fitted one."""
    if model.posterior_ is None or model.transform_ is None or model.index_ is None:
        raise ArtifactError("Modèle non ajusté : rien à persister")
    if model.sampler.fast:
        raise ArtifactError("Artefact refusé pour un ajustement --fast (sous-échantillon)")
    frame = design_frame(train)
    expected = _transform_summary(model.transform_)
    if _transform_summary(build_design(frame, FIXED_SPEC).transform) != expected:
        raise ArtifactError("Transform non reproductible depuis les colonnes de features")
    run_id = f"{model.name}-{datetime.now(UTC).strftime('%Y%m%dT%H%M%SZ')}"
    directory = root / run_id
    directory.mkdir(parents=True, exist_ok=False)
    draws = model.posterior_.draws
    np.savez(directory / "draws.npz", **{k: draws[k] for k in (*_STORED_DRAWS, *_SIGMAS)})  # type: ignore[arg-type]
    frame.write_parquet(directory / "design_frame.parquet")
    index = model.index_
    meta = {
        "artifact_version": ARTIFACT_VERSION,
        "run_id": run_id,
        "model_name": model.name,
        "created_at": datetime.now(UTC).isoformat(),
        "dataset_version": dataset_version,
        "git_sha": git_sha,
        "seasons": list(seasons),
        "n_train_rows": len(train),
        "ipw": model.ipw,
        "diagnostics": asdict(model.diagnostics_) if model.diagnostics_ else None,
        "index": {
            "codes": list(index.codes),
            "groups": list(index.groups),
            "units": list(index.units),
            "group_of_code": index.group_of_code.tolist(),
            "unit_of_group": index.unit_of_group.tolist(),
        },
        "profiles": model.profiles_,
        "transform": expected,
    }
    (directory / "meta.json").write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return directory


def latest_artifact(root: Path = MODELS_DIR) -> Path:
    candidates = sorted(p for p in root.glob("*/meta.json")) if root.exists() else []
    if not candidates:
        raise ArtifactError(f"Aucun artefact dans {root} : lancer `rugby-risk fit-final`")
    return max(candidates, key=lambda p: p.stat().st_mtime).parent


def is_promoted(directory: Path) -> bool:
    return (directory / PROMOTION_FILE).exists()


def load_hierarchical(directory: Path) -> tuple[HierarchicalHazardModel, dict[str, Any]]:
    """Rebuild a predict-only M2 (new players / team-seasons integrated)."""
    meta_path = directory / "meta.json"
    if not meta_path.exists():
        raise ArtifactError(f"Artefact introuvable : {meta_path}")
    meta: dict[str, Any] = json.loads(meta_path.read_text(encoding="utf-8"))
    if meta.get("artifact_version") != ARTIFACT_VERSION:
        raise ArtifactError(f"Version d'artefact non supportée : {meta.get('artifact_version')}")
    frame = pl.read_parquet(directory / "design_frame.parquet")
    transform = build_design(frame, FIXED_SPEC).transform
    if _transform_summary(transform) != meta["transform"]:
        raise ArtifactError("Transform reconstruit différent de l'ajustement (artefact altéré)")
    with np.load(directory / "draws.npz") as npz:
        draws = {k: np.asarray(npz[k], dtype=float) for k in (*_STORED_DRAWS, *_SIGMAS)}
    n_draws = len(draws["alpha"])
    for key in _EMPTY_EFFECTS:  # profils = toujours nouveaux joueur / équipe-saison
        draws[key] = np.zeros((n_draws, 0))
    model = HierarchicalHazardModel(ipw=bool(meta["ipw"]), name=str(meta["model_name"]))
    idx = meta["index"]
    model.index_ = _Index(
        codes=tuple(idx["codes"]),
        groups=tuple(idx["groups"]),
        units=tuple(idx["units"]),
        group_of_code=np.asarray(idx["group_of_code"], dtype=int),
        unit_of_group=np.asarray(idx["unit_of_group"], dtype=int),
        players={},
        teams={},
    )
    model.transform_ = transform
    model.posterior_ = _Posterior(draws)
    model.profiles_ = {str(k): dict(v) for k, v in meta["profiles"].items()}
    model.n_train_rows_ = int(meta["n_train_rows"])
    if meta.get("diagnostics"):
        model.diagnostics_ = McmcDiagnostics(**meta["diagnostics"])
    return model, meta
