"""Public aggregated tables (F25, docs/04 §5) from a local M2 artifact and the ML export.

Inputs stay local (the ML export carries `player_key`); outputs are per-position aggregates
only and still go through `serving/guard.make_public` before any write (`export.publish`).

- `pred_position_curve`: posterior mean and 90 % credible band of h(N), N = 0..15, per
  position and scenario, plus the cumulative risk over a run of N+1 matches started at 0
  (computed per posterior draw, so the band is exact, not a product of bounds).
- `pred_position_season`: observed incidence of the ML label (injuries with >= 2 missed
  matches) per 1000 h, exact Poisson 90 % interval, bucketed injury count.
- `calibration_public` / `model_registry_public`: from the rolling-origin experiment
  summaries (`reports/experiments/<run_id>_summary.json`), never from the final fit (which
  is not scored on its own rows).
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Final, Protocol

import numpy as np
import polars as pl
from scipy import stats

from rugby_risk.modeling.curves import Scenarios, hazard_curve_draws
from rugby_risk.serving.guard import make_public

CI_LEVEL: Final = 0.90
SUMMARY_SUFFIX: Final = "_summary.json"
COUNT_BUCKETS: Final = ((10, "<10"), (25, "10-24"), (50, "25-49"))
TABLES: Final = (
    "pred_position_curve",
    "pred_position_season",
    "calibration_public",
    "model_registry_public",
)
PUBLIC_WARNING: Final = (
    "Association statistique, non causale. Ordres de grandeur par poste issus de données "
    "publiques (blessures avec arrêt d'au moins 2 matchs, sous-déclarées) : ce n'est ni un "
    "diagnostic ni une prédiction individuelle, et cela ne remplace pas l'avis du staff "
    "médical."
)


class PublishError(RuntimeError):
    """Inputs inconsistent (dataset version, missing evaluation summary...)."""


class DrawModel(Protocol):
    profiles_: dict[str, dict[str, Any]]
    scenarios_: Scenarios

    def predict_draws(self, df: pl.DataFrame) -> np.ndarray: ...


@dataclass(frozen=True)
class PublicTables:
    model_version: str
    dataset_version: str
    promoted: bool
    computed_at: str
    tables: dict[str, pl.DataFrame]


def count_bucket(n: int) -> str:
    for upper, label in COUNT_BUCKETS:
        if n < upper:
            return label
    return "50+"


def poisson_interval(events: int, level: float = CI_LEVEL) -> tuple[float, float]:
    """Exact (Garwood) interval of a Poisson count."""
    alpha = 1 - level
    low = 0.0 if events == 0 else float(stats.chi2.ppf(alpha / 2, 2 * events) / 2)
    high = float(stats.chi2.ppf(1 - alpha / 2, 2 * events + 2) / 2)
    return low, high


def position_support(rows: pl.DataFrame) -> dict[str, int]:
    """Distinct players per position in the estimation rows (k-anonymity support)."""
    agg = rows.group_by("position_code").agg(pl.col("player_key").n_unique().alias("n"))
    return {str(r["position_code"]): int(r["n"]) for r in agg.iter_rows(named=True)}


def position_curves(
    model: DrawModel,
    support: dict[str, int],
    *,
    model_version: str,
    season_id: str,
    computed_at: str,
) -> pl.DataFrame:
    lo_q, hi_q = (1 - CI_LEVEL) / 2, (1 + CI_LEVEL) / 2
    records: list[dict[str, Any]] = []
    for code in sorted(model.profiles_):
        for scenario in sorted(model.scenarios_.overrides):
            draws = hazard_curve_draws(model, code, scenario=scenario)  # (tirages, N)
            cumulative = 1.0 - np.cumprod(1.0 - draws, axis=1)
            for i, n in enumerate(model.scenarios_.n_range):
                h, c = draws[:, i], cumulative[:, i]
                records.append(
                    {
                        "model_version": model_version,
                        "season_id": season_id,
                        "position_code": code,
                        "n_consecutive": int(n),
                        "scenario": scenario,
                        "p_mean": float(h.mean()),
                        "p_low90": float(np.quantile(h, lo_q)),
                        "p_high90": float(np.quantile(h, hi_q)),
                        "cum_mean": float(c.mean()),
                        "cum_low90": float(np.quantile(c, lo_q)),
                        "cum_high90": float(np.quantile(c, hi_q)),
                        "n_players_support": int(support.get(code, 0)),
                        "computed_at": computed_at,
                    }
                )
    return pl.DataFrame(records)


def position_seasons(
    rows: pl.DataFrame,
    groups: dict[str, str],
    *,
    model_version: str,
    computed_at: str,
    target_col: str = "y_injury",
) -> pl.DataFrame:
    agg = (
        rows.group_by(["season_id", "position_code"])
        .agg(
            pl.col(target_col).cast(pl.Int64).sum().alias("injuries"),
            (pl.col("minutes_played").cast(pl.Float64).sum() / 60.0).alias("exposure_hours"),
            pl.len().alias("n_matches_played"),
            pl.col("player_key").n_unique().alias("n_players_support"),
        )
        .sort(["season_id", "position_code"])
    )
    records: list[dict[str, Any]] = []
    for r in agg.iter_rows(named=True):
        hours = float(r["exposure_hours"])
        events = int(r["injuries"])
        low, high = poisson_interval(events)
        scale = 1000.0 / hours if hours > 0 else float("nan")
        records.append(
            {
                "model_version": model_version,
                "season_id": str(r["season_id"]),
                "position_code": str(r["position_code"]),
                "position_group": groups.get(str(r["position_code"]), "unknown"),
                "incidence_per_1000h": events * scale,
                "incidence_low90": low * scale,
                "incidence_high90": high * scale,
                "injuries_count_bucket": count_bucket(events),
                "exposure_hours": round(hours, 1),
                "n_matches_played": int(r["n_matches_played"]),
                "n_players_support": int(r["n_players_support"]),
                "computed_at": computed_at,
            }
        )
    return pl.DataFrame(records)


# --- résumés d'expérience (rolling origin) ---------------------------------------------------


def load_summary(path: Path) -> dict[str, Any]:
    summary: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    return summary


def latest_summary(directory: Path, model_name: str, dataset_version: str) -> dict[str, Any]:
    """Most recent experiment summary of `model_name` on the same dataset version."""
    candidates = []
    for path in sorted(directory.glob(f"{model_name}-*{SUMMARY_SUFFIX}")):
        summary = load_summary(path)
        if summary.get("model_name") == model_name and (
            summary.get("dataset_version") == dataset_version
        ):
            candidates.append(summary)
    if not candidates:
        raise PublishError(
            f"Aucun résumé d'évaluation {model_name} sur dataset_version={dataset_version}"
            f" dans {directory} : lancer `rugby-risk train {model_name}`"
        )
    return max(candidates, key=lambda s: str(s["run_id"]))


def calibration_rows(summary: dict[str, Any], model_version: str) -> pl.DataFrame:
    test = ",".join(str(f["test_season"]) for f in summary["folds"])
    return pl.DataFrame(
        [
            {
                "model_version": model_version,
                "test_season": test,
                "position_group": str(b["position_group"]),
                "bin": int(b["bin"]),
                "p_pred_mean": float(b["p_pred_mean"]),
                "p_obs": float(b["p_obs"]),
                "n": int(b["n"]),
                "n_players_support": int(b["n_players_support"]),
            }
            for b in summary["calibration"]
        ]
    )


def registry_row(  # noqa: PLR0913 - une ligne de registre par modèle évalué
    summary: dict[str, Any],
    *,
    model_version: str,
    role: str,
    promoted: bool,
    train_seasons: str,
    trained_at: str,
    notes: str,
) -> dict[str, Any]:
    m = summary["aggregated"]
    return {
        "model_version": model_version,
        "model_name": str(summary["model_name"]),
        "role": role,
        "promoted": promoted,
        "trained_at": trained_at,
        "train_seasons": train_seasons,
        "test_season": ",".join(str(f["test_season"]) for f in summary["folds"]),
        "dataset_version": str(summary["dataset_version"]),
        "n_test": int(m["n"]),
        "brier": m.get("brier"),
        "brier_low90": summary.get("brier_boot_low"),
        "brier_high90": summary.get("brier_boot_high"),
        "brier_skill": m.get("brier_skill"),
        "logloss": m.get("log_loss"),
        "auc_roc": m.get("auc_roc"),
        "calib_slope": m.get("calibration_slope"),
        "calib_intercept": m.get("calibration_intercept"),
        "notes": notes,
    }


def summary_train_seasons(summary: dict[str, Any]) -> str:
    seasons = sorted({s for f in summary["folds"] for s in f["train_seasons"]})
    return ",".join(seasons)


# --- orchestration ---------------------------------------------------------------------------


def build_public_tables(
    artifact_directory: Path,
    df: pl.DataFrame,
    *,
    ml_config: Any = None,
    experiments_dir: Path = Path("reports/experiments"),
    evaluation_models: tuple[tuple[str, str], ...] = (
        ("m2_hierarchical", "principale"),
        ("m0_position", "référence"),
        ("m1_hazard_cloglog", "challenger paramétrique"),
        ("m1w_hazard_ipw", "challenger IPW"),
        ("m3_gbm", "challenger non paramétrique"),
    ),
) -> PublicTables:
    """The four public tables (docs/04 §5) from a local M2 artifact and the ML export.

    `df` still carries `player_key`: it only feeds per-position counts. Every output table
    goes through `make_public` (columns, then k-anonymity) before leaving this module.
    A model without a rolling-origin evaluation summary cannot publish its calibration.
    """
    from rugby_risk.modeling.artifact import (  # noqa: PLC0415 - import paresseux
        is_promoted,
        load_hierarchical,
    )
    from rugby_risk.modeling.profile import NOT_PROMOTED  # noqa: PLC0415
    from rugby_risk.modeling.runner import estimation_rows  # noqa: PLC0415

    model, meta = load_hierarchical(artifact_directory)
    if model.status != "ok":
        raise PublishError(f"MCMC du modèle en échec (statut {model.status}) : export refusé")
    model_version = str(meta["run_id"])
    dataset_version = str(meta["dataset_version"])
    computed_at = str(meta["created_at"])
    promoted = is_promoted(artifact_directory)
    train_seasons = tuple(str(s) for s in meta["seasons"])

    rows = estimation_rows(df, train_seasons, ml_config)
    if str(rows["dataset_version"][0]) != dataset_version:
        raise PublishError(
            f"Version d'export ML ({rows['dataset_version'][0]}) != version de l'artefact"
            f" ({dataset_version}) : re-fitter ou re-générer l'export"
        )
    support = position_support(rows)
    groups = _position_groups()
    season_id = "+".join(train_seasons)

    curve = position_curves(
        model,
        support,
        model_version=model_version,
        season_id=season_id,
        computed_at=computed_at,
    )
    season = position_seasons(rows, groups, model_version=model_version, computed_at=computed_at)

    evaluation = latest_summary(experiments_dir, "m2_hierarchical", dataset_version)
    calibration = calibration_rows(evaluation, model_version)
    registry_records = [
        registry_row(
            evaluation,
            model_version=model_version,
            role="principale",
            promoted=promoted,
            train_seasons=summary_train_seasons(evaluation),
            trained_at=computed_at,
            notes=("" if promoted else f"{NOT_PROMOTED} ") + PUBLIC_WARNING,
        )
    ]
    for name, role in evaluation_models:
        if name == "m2_hierarchical":
            continue
        other = latest_summary(experiments_dir, name, dataset_version)
        registry_records.append(
            registry_row(
                other,
                model_version=f"{name}:{other['run_id']}",
                role=role,
                promoted=False,
                train_seasons=summary_train_seasons(other),
                trained_at=str(other.get("created_at", "")),
                notes=PUBLIC_WARNING,
            )
        )
    registry = pl.DataFrame(registry_records)

    tables = {
        "pred_position_curve": make_public(curve, table="pred_position_curve"),
        "pred_position_season": make_public(season, table="pred_position_season"),
        "calibration_public": make_public(calibration, table="calibration_public"),
        "model_registry_public": make_public(
            registry, table="model_registry_public", aggregated=False
        ),
    }
    return PublicTables(
        model_version=model_version,
        dataset_version=dataset_version,
        promoted=promoted,
        computed_at=computed_at,
        tables=tables,
    )


def _position_groups() -> dict[str, str]:
    from rugby_risk.reference import positions  # noqa: PLC0415

    return {
        str(r["position_code"]): str(r["position_group"]) for r in positions().iter_rows(named=True)
    }
