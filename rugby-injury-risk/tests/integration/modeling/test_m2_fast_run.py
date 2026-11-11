"""F22 integration : M2 complet dans le runner F18 (folds par saison, rapports, MLflow)."""

from pathlib import Path

import pytest

from rugby_risk.modeling.hierarchical import FAST_SAMPLER, HierarchicalHazardModel
from rugby_risk.modeling.runner import ExperimentConfig, run_experiment
from tests.hazard_factory import hierarchical_frame

pytestmark = [pytest.mark.integration, pytest.mark.slow]


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
    df = hierarchical_frame(players=400, seasons=4, matches=20, seed=0, slope_forward=0.15)
    return run_experiment(
        lambda: HierarchicalHazardModel(sampler=FAST_SAMPLER, ipw=False, seed=0),
        df,
        _config(tmp_path_factory.mktemp("m2")),
    )


def test_m2_runs_across_season_folds(result) -> None:
    assert result.model_name == "m2_hierarchical"
    assert len(result.folds) == 2  # 4 saisons, min_train_seasons=1 -> folds (1,1),(1,2) test
    assert result.aggregated.brier_skill is not None


def test_report_has_m2_sections_and_no_player_ids(result) -> None:
    text = result.report_path.read_text(encoding="utf-8")
    assert "Courbes h(N) par poste" in text
    assert "M2 : diagnostics MCMC" in text
    assert "M2 : prior predictive check" in text
    assert "Labels censurés exclus" in text
    assert "player_key" not in text and "p0" not in text
    assert (result.report_path.parent / f"{result.run_id}_hazard_curves.png").exists()


def test_fast_mode_and_prior_check_logged(result) -> None:
    params = result.extra["params"]
    assert params["fast"] is True
    assert params["prior_check_ok"] is True
    assert params["mcmc_status"] in {"ok", "failed"}
    assert result.extra["run_status"] == params["mcmc_status"]
    assert result.extra["registry_name"] == "rugby-risk-m2"
