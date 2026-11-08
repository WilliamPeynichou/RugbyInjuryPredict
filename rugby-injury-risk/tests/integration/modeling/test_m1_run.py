"""F20 integration: M1 through the F18 runner (synthetic load effect + real dbt schema)."""

from pathlib import Path

import duckdb
import polars as pl
import pytest

from rugby_risk.modeling.hazard import DiscreteHazardModel
from rugby_risk.modeling.runner import ExperimentConfig, run_experiment
from tests.factories import build_ml, make_league
from tests.hazard_factory import hazard_frame

pytestmark = pytest.mark.integration


def _config(tmp: Path) -> ExperimentConfig:
    return ExperimentConfig(
        min_train_seasons=1,
        bootstrap_replications=30,
        seed=0,
        mlflow_uri=f"sqlite:///{tmp}/mlflow.db",
        min_label_followup=2,
    )


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    df = hazard_frame(
        players=500, seasons=3, base=-3.6, beta_forward=0.12, beta_back=0.04, beta_min28=0.3
    )
    return run_experiment(
        lambda: DiscreteHazardModel(curve_replications=10),
        df,
        _config(tmp_path_factory.mktemp("mlflow")),
    )


def test_m1_beats_m0_with_load_effects(result) -> None:
    assert result.model_name == "m1_hazard_cloglog"
    assert result.aggregated.brier_skill is not None
    assert result.aggregated.brier_skill > 0
    for fold in result.folds:
        assert fold.metrics.brier_skill is not None and fold.metrics.brier_skill > 0


def test_report_has_curves_and_figure(result) -> None:
    text = result.report_path.read_text(encoding="utf-8")
    assert "Courbes h(N) par poste" in text and "réplications" in text
    assert "Labels censurés exclus" in text
    assert "player_key" not in text and "p0001" not in text
    assert (result.report_path.parent / f"{result.run_id}_hazard_curves.png").exists()
    # 2 dernières lignes de chaque joueur-saison : label non observable.
    assert result.extra["censored_played_rows"] == 500 * 3 * 2


def test_runs_on_real_ml_table_schema(tmp_path_factory) -> None:
    """Every column dtype of the dbt `ml_player_match` goes through the design."""
    league = make_league(seasons=3, seed=2)
    warehouse = tmp_path_factory.mktemp("m1") / "w.duckdb"
    assert build_ml(warehouse, tmp_path_factory.mktemp("dbt"), league)
    with duckdb.connect(str(warehouse)) as con:
        df = pl.from_arrow(con.execute("select * from ml_player_match").to_arrow_table())
    out = run_experiment(
        lambda: DiscreteHazardModel(curve_replications=3),
        df,
        _config(tmp_path_factory.mktemp("mlflow")),
    )
    assert out.aggregated.n > 0
    assert out.extra["params"]["converged"] is True
