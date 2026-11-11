"""F25 batch: public tables keep the docs/04 §5 schema and contain no identifier."""

import json
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any

import numpy as np
import polars as pl
import pytest

from rugby_risk.modeling.curves import Scenarios
from rugby_risk.serving.batch import (
    TABLES,
    PublicTables,
    PublishError,
    build_public_tables,
    count_bucket,
    latest_summary,
    poisson_interval,
    position_curves,
    position_seasons,
    registry_row,
    summary_train_seasons,
)
from rugby_risk.serving.guard import FORBIDDEN_PUBLIC_COLUMNS, MIN_SUPPORT

pytestmark = pytest.mark.unit


class FakeDrawModel:
    def __init__(self, n_draws: int = 50) -> None:
        self.profiles_ = {
            "PROP": {"consecutive_matches": 1.0, "minutes_played": 80.0},
            "HOOKER": {"consecutive_matches": 1.0, "minutes_played": 80.0},
        }
        self.scenarios_ = Scenarios(
            minutes_played=80.0,
            n_range=(0, 1, 2),
            overrides={"median": {}, "short_turnaround_block": {"short_turnaround": 1.0}},
        )
        rng = np.random.default_rng(0)
        self.draws = rng.beta(2, 50, size=(n_draws, 3))
        self.status = "ok"

    def predict_draws(self, df: pl.DataFrame) -> np.ndarray:  # modèle factice : ignore le frame
        return self.draws


def test_count_bucket() -> None:
    assert count_bucket(0) == "<10"
    assert count_bucket(9) == "<10"
    assert count_bucket(10) == "10-24"
    assert count_bucket(24) == "10-24"
    assert count_bucket(25) == "25-49"
    assert count_bucket(49) == "25-49"
    assert count_bucket(50) == "50+"


def test_poisson_interval_exact() -> None:
    low, high = poisson_interval(0)
    assert low == 0.0 and high > 0
    low, high = poisson_interval(20)
    assert 0 < low < 20 < high
    # Largeur totale (~18,6/1000h à 20 événements) bornée : pas d'intervalle dégénéré.
    assert high < 20 * 3


def test_position_curves_schema_and_values() -> None:
    model = FakeDrawModel()
    support = {"PROP": 120, "HOOKER": MIN_SUPPORT}
    frame = position_curves(
        model, support, model_version="m2_test", season_id="2022+2023", computed_at="t"
    )
    assert frame.height == 2 * 2 * 3  # postes x scénarios x N
    assert {"p_mean", "p_low90", "p_high90", "cum_mean", "cum_low90", "cum_high90"} <= set(
        frame.columns
    )
    assert {c.lower() for c in frame.columns}.isdisjoint(FORBIDDEN_PUBLIC_COLUMNS)
    assert (frame["n_players_support"] >= MIN_SUPPORT).all()
    # Cumulé à N=2 >= cumulé à N=1 (hazards positifs) pour le scénario médian.
    median = frame.filter(pl.col("scenario") == "median", pl.col("position_code") == "PROP").sort(
        "n_consecutive"
    )
    assert (median["cum_mean"].to_numpy()[1:] >= median["cum_mean"].to_numpy()[:-1]).all()


def test_position_seasons_incidence_and_groups() -> None:
    rng = np.random.default_rng(1)
    rows = pl.DataFrame(
        {
            "season_id": ["2022-2023"] * 20 + ["2023-2024"] * 20,
            "position_code": ["PROP"] * 20 + ["HOOKER"] * 20,
            "y_injury": rng.integers(0, 2, 20).tolist() + rng.integers(0, 2, 20).tolist(),
            "minutes_played": [80.0] * 40,
            "player_key": [f"p{i}" for i in range(40)],
        }
    )
    frame = position_seasons(
        rows, {"PROP": "front_row", "HOOKER": "front_row"}, model_version="m", computed_at="t"
    )
    assert frame.height == 2
    assert set(frame["position_group"]) == {"front_row"}
    prop = frame.filter(pl.col("position_code") == "PROP").row(0, named=True)
    assert prop["incidence_low90"] <= prop["incidence_per_1000h"] <= prop["incidence_high90"]
    assert prop["exposure_hours"] == pytest.approx(20 * 80 / 60, abs=0.5)
    assert {c.lower() for c in frame.columns}.isdisjoint(FORBIDDEN_PUBLIC_COLUMNS)


_SUMMARY = {
    "run_id": "m2_test-20260101T000000Z",
    "model_name": "m2_hierarchical",
    "dataset_version": "ds1",
    "git_sha": "abc",
    "created_at": "2026-01-01T00:00:00+00:00",
    "folds": [
        {
            "train_seasons": ["2022-2023"],
            "valid_season": "2023-2024",
            "test_season": "2024-2025",
        }
    ],
    "aggregated": {"n": 100, "brier": 0.02, "brier_skill": 0.01, "log_loss": 0.1},
    "brier_boot_low": 0.015,
    "brier_boot_high": 0.025,
    "calibration": [
        {
            "position_group": "all",
            "bin": 0,
            "p_pred_mean": 0.02,
            "p_obs": 0.03,
            "n": 500,
            "n_players_support": 40,
        }
    ],
}


def _write_summary(tmp_path: Path, name: str) -> Path:
    path = tmp_path / name
    path.write_text(__import__("json").dumps(_SUMMARY), encoding="utf-8")
    return path


def test_latest_summary_filters_dataset_version(tmp_path: Path) -> None:
    _write_summary(tmp_path, "m2_hierarchical-20260101T000000Z_summary.json")
    other = dict(_SUMMARY, dataset_version="autre")
    (tmp_path / "m2_hierarchical-20260102T000000Z_summary.json").write_text(
        __import__("json").dumps(other), encoding="utf-8"
    )
    summary = latest_summary(tmp_path, "m2_hierarchical", "ds1")
    assert summary["run_id"] == "m2_test-20260101T000000Z"


def test_summary_train_seasons() -> None:
    assert summary_train_seasons(_SUMMARY) == "2022-2023"


def test_registry_row_shape() -> None:
    row = registry_row(
        _SUMMARY,
        model_version="m2_test",
        role="principale",
        promoted=False,
        train_seasons="2022-2023",
        trained_at="t",
        notes="non promu",
    )
    assert row["promoted"] is False
    assert row["brier"] == 0.02
    assert row["test_season"] == "2024-2025"
    assert row["dataset_version"] == "ds1"


def test_public_tables_container() -> None:
    tables = PublicTables(
        model_version="m",
        dataset_version="ds",
        promoted=False,
        computed_at="t",
        tables={"model_registry_public": pl.DataFrame([{"model_version": "m"}])},
    )
    assert not tables.promoted


# --- build_public_tables de bout en bout (sans MCMC : faux modèle à tirages) -----------------

_DATASET = "7d004d9a146715b139e501738e58620a"
_MODELS = ("m2_hierarchical", "m0_position", "m1_hazard_cloglog", "m1w_hazard_ipw", "m3_gbm")


def _estimation_frame() -> pl.DataFrame:
    """12 joueurs PROP, 12 HOOKER, 3 WING (sous k=10), 6 matchs chacun, une saison."""
    start = datetime(2022, 9, 1)
    rows: list[dict[str, Any]] = []
    groups = {"PROP": 12, "HOOKER": 12, "WING": 3}
    for code, n_players in groups.items():
        for i in range(n_players):
            for m in range(6):
                rows.append(
                    {
                        "player_key": f"{code}-{i}",
                        "season_id": "2022-2023",
                        "position_code": code,
                        "kickoff_ts": start + timedelta(days=7 * m),
                        "played": True,
                        "minutes_played": 80.0,
                        "y_injury": int(i == 0 and m == 0),
                        "dataset_version": _DATASET,
                    }
                )
    return pl.DataFrame(rows)


def _write_experiments(directory: Path, *, dataset: str = _DATASET, skip: str = "") -> None:
    for name in _MODELS:
        if name == skip:
            continue
        summary = dict(_SUMMARY, model_name=name, run_id=f"{name}-20260101T000000Z")
        summary["dataset_version"] = dataset
        (directory / f"{name}-20260101T000000Z_summary.json").write_text(
            json.dumps(summary), encoding="utf-8"
        )


@pytest.fixture
def patched_artifact(monkeypatch: pytest.MonkeyPatch) -> dict[str, Any]:
    state: dict[str, Any] = {
        "model": FakeDrawModel(),
        "meta": {
            "run_id": "m2_test-20260101T000000Z",
            "dataset_version": _DATASET,
            "created_at": "2026-01-01T00:00:00+00:00",
            "seasons": ["2022-2023"],
        },
        "promoted": False,
    }
    monkeypatch.setattr(
        "rugby_risk.modeling.artifact.load_hierarchical",
        lambda _directory: (state["model"], state["meta"]),
    )
    monkeypatch.setattr(
        "rugby_risk.modeling.artifact.is_promoted", lambda _directory: state["promoted"]
    )
    return state


def test_build_public_tables_four_safe_tables(
    tmp_path: Path, patched_artifact: dict[str, Any]
) -> None:
    _write_experiments(tmp_path)
    public = build_public_tables(tmp_path, _estimation_frame(), experiments_dir=tmp_path)
    assert set(public.tables) == set(TABLES)
    assert public.model_version == "m2_test-20260101T000000Z"
    assert public.dataset_version == _DATASET
    assert public.promoted is False
    for name, frame in public.tables.items():
        assert {c.lower() for c in frame.columns}.isdisjoint(FORBIDDEN_PUBLIC_COLUMNS), name
        if "n_players_support" in frame.columns:
            assert (frame["n_players_support"] >= MIN_SUPPORT).all(), name
    # WING (3 joueurs, sous k=10) est supprimé par le garde-fou k-anonymat dans la table saison.
    assert set(public.tables["pred_position_curve"]["position_code"]) == {"PROP", "HOOKER"}
    assert set(public.tables["pred_position_season"]["position_code"]) == {"PROP", "HOOKER"}
    registry = public.tables["model_registry_public"]
    assert registry.height == len(_MODELS)
    assert registry.filter(pl.col("role") == "principale")["promoted"].to_list() == [False]


def test_build_public_tables_refuses_dataset_mismatch(
    tmp_path: Path, patched_artifact: dict[str, Any]
) -> None:
    _write_experiments(tmp_path)
    patched_artifact["meta"]["dataset_version"] = "autre-version"
    with pytest.raises(PublishError):
        build_public_tables(tmp_path, _estimation_frame(), experiments_dir=tmp_path)


def test_build_public_tables_refuses_failed_mcmc(
    tmp_path: Path, patched_artifact: dict[str, Any]
) -> None:
    _write_experiments(tmp_path)
    patched_artifact["model"].status = "divergences"
    with pytest.raises(PublishError, match="statut"):
        build_public_tables(tmp_path, _estimation_frame(), experiments_dir=tmp_path)


def test_build_public_tables_requires_evaluation_summary(
    tmp_path: Path, patched_artifact: dict[str, Any]
) -> None:
    with pytest.raises(PublishError, match="résumé"):
        build_public_tables(tmp_path, _estimation_frame(), experiments_dir=tmp_path)
