"""F21 integration: M1w (hazard + IPW) through the F18 runner (synthetic + real dbt schema)."""

from pathlib import Path

import duckdb
import polars as pl
import pytest

from rugby_risk.modeling.runner import ExperimentConfig, run_experiment
from rugby_risk.modeling.selection import WeightedHazardModel
from tests.factories import build_ml, make_league
from tests.hazard_factory import selection_frame

pytestmark = pytest.mark.integration


def _config(tmp: Path) -> ExperimentConfig:
    return ExperimentConfig(
        min_train_seasons=1,
        bootstrap_replications=30,
        seed=0,
        mlflow_uri=f"sqlite:///{tmp}/mlflow.db",
        reports_dir=tmp / "experiments",
        min_label_followup=2,
    )


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    df = selection_frame(players=400, seasons=3, seed=3)
    return run_experiment(
        lambda: WeightedHazardModel(curve_replications=10, truncate=(0.001, 0.999)),
        df,
        _config(tmp_path_factory.mktemp("mlflow")),
    )


def test_m1w_runs_with_ipw(result) -> None:
    assert result.model_name == "m1w_hazard_ipw"
    assert result.aggregated.n > 0
    assert result.extra["params"]["ipw_enabled"] in (True, False)
    assert result.extra["params"]["selection_features"] > 0


def test_report_has_ipw_diagnostics_and_figure(result) -> None:
    text = result.report_path.read_text(encoding="utf-8")
    assert "Diagnostics IPW" in text
    assert "M1 vs M1w" in text
    assert "Poids IPW stabilisés" in text
    assert "player_key" not in text and "p0001" not in text
    assert (result.report_path.parent / f"{result.run_id}_hazard_curves_ipw.png").exists()


def test_runs_on_real_ml_table_schema(tmp_path_factory) -> None:
    """Every column dtype of the dbt `ml_player_match` goes through selection + design."""
    league = make_league(seasons=3, seed=2)
    warehouse = tmp_path_factory.mktemp("m1w") / "w.duckdb"
    assert build_ml(warehouse, tmp_path_factory.mktemp("dbt"), league)
    with duckdb.connect(str(warehouse)) as con:
        df = pl.from_arrow(con.execute("select * from ml_player_match").to_arrow_table())
    out = run_experiment(
        lambda: WeightedHazardModel(curve_replications=3),
        df,
        _config(tmp_path_factory.mktemp("mlflow")),
    )
    assert out.aggregated.n > 0
    assert out.extra["params"]["selection_slope"] is not None
