"""Garde-fou : un run d'expérience synthétique ne doit rien écrire dans le dépôt.

`run_experiment` écrit ses rapports dans `config.reports_dir`. Les tests passent `tmp_path` ;
ce test vérifie que `reports/experiments` du dépôt est inchangé après un run complet.
"""

from pathlib import Path

import duckdb
import polars as pl
import pytest

from rugby_risk.modeling.null import ConstantModel
from rugby_risk.modeling.runner import ExperimentConfig, run_experiment
from tests.factories import build_ml, make_league

pytestmark = pytest.mark.integration

REPO_EXPERIMENTS = Path(__file__).resolve().parents[2] / "reports" / "experiments"


def _listing(directory: Path) -> set[str]:
    if not directory.exists():
        return set()
    return {str(p.relative_to(directory)) for p in directory.rglob("*")}


def _ml_frame(warehouse: Path) -> pl.DataFrame:
    with duckdb.connect(str(warehouse)) as con:
        return pl.from_arrow(
            con.execute(
                """select season_id, played, y_injury, player_key, dataset_version, kickoff_ts,
                          minutes_played
                   from ml_player_match"""
            ).to_arrow_table()
        )


def test_synthetic_run_writes_nothing_into_repo(tmp_path_factory) -> None:
    before = _listing(REPO_EXPERIMENTS)
    league = make_league(seasons=3, seed=2)
    warehouse = tmp_path_factory.mktemp("pollution") / "w.duckdb"
    assert build_ml(warehouse, tmp_path_factory.mktemp("dbt"), league)
    df = _ml_frame(warehouse)
    tmp = tmp_path_factory.mktemp("run")
    config = ExperimentConfig(
        min_train_seasons=1,
        bootstrap_replications=20,
        seed=0,
        mlflow_uri=f"sqlite:///{tmp}/mlflow.db",
        reports_dir=tmp / "experiments",
    )
    result = run_experiment(lambda: ConstantModel(), df, config)  # noqa: PLW0108 - factory
    assert result.report_path.is_relative_to(tmp), "le rapport doit être dans tmp_path"
    assert _listing(REPO_EXPERIMENTS) == before, "un run synthétique a pollué le dépôt"


def test_reports_dir_accepts_str_and_path(tmp_path: Path) -> None:
    as_str = ExperimentConfig(reports_dir=str(tmp_path))  # type: ignore[arg-type]
    as_path = ExperimentConfig(reports_dir=tmp_path)
    assert as_str.reports_dir == as_path.reports_dir == tmp_path
    assert isinstance(as_str.reports_dir, Path)
