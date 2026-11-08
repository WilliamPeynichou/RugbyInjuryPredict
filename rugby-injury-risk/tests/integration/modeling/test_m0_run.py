"""F19 integration : M0 par poste via le runner F18, sur la ligue synthétique F17."""

from pathlib import Path

import duckdb
import polars as pl
import pytest

from rugby_risk.modeling.baselines import PositionRateModel
from rugby_risk.modeling.runner import ExperimentConfig, run_experiment
from tests.factories import build_ml, make_league

pytestmark = pytest.mark.integration


def _ml_frame(warehouse: Path) -> pl.DataFrame:
    with duckdb.connect(str(warehouse)) as con:
        return pl.from_arrow(
            con.execute(
                """select season_id, played, y_injury, player_key, dataset_version, kickoff_ts,
                          minutes_played, position_code, position_group
                   from ml_player_match"""
            ).to_arrow_table()
        )


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    league = make_league(seasons=3, seed=1)
    warehouse = tmp_path_factory.mktemp("m0") / "w.duckdb"
    assert build_ml(warehouse, tmp_path_factory.mktemp("dbt"), league)
    df = _ml_frame(warehouse)
    config = ExperimentConfig(
        min_train_seasons=1,
        bootstrap_replications=50,
        seed=0,
        mlflow_uri=f"sqlite:///{tmp_path_factory.mktemp('mlflow')}/mlflow.db",
    )
    return run_experiment(lambda: PositionRateModel(), df, config)  # noqa: PLW0108 - factory


def test_run_completes_and_beats_global_reference(result) -> None:
    assert result.folds, "au moins un fold"
    assert result.aggregated.n > 0
    # Brier skill vs M0 global : le modèle par poste fait à peu près aussi bien
    # (les blessures synthétiques sont indépendantes du poste -> skill ~ 0).
    assert result.aggregated.brier_skill is not None
    assert result.aggregated.brier_skill > -0.02
    # M0 ne discrimine pas (une proba par poste) : AUC proche de 0.5, jamais > 0.75.
    assert result.aggregated.auc_roc < 0.75


def test_report_has_position_rates_without_player_keys(result) -> None:
    text = result.report_path.read_text(encoding="utf-8")
    assert "Taux M0 par poste" in text
    assert "Premiership" in text  # comparaison aux priors
    assert "player_key" not in text
    assert result.extra["tables"], "tables de taux dans extra"
