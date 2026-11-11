"""F23 intégration : run M3 complet via le runner + SHAP retrouve l'interaction simulée."""

import time

import numpy as np
import polars as pl
import pytest

from rugby_risk.modeling.gbm import GBMRiskModel, _shap_numeric
from rugby_risk.modeling.runner import ExperimentConfig, run_experiment
from tests.hazard_factory import hazard_frame

pytestmark = pytest.mark.integration


def _df(seasons: int = 3, seed: int = 5) -> pl.DataFrame:
    # Interaction unit x consecutive simulée : pente forte chez les avants, nulle chez les arrières.
    return hazard_frame(
        players=120, seasons=seasons, matches=10, seed=seed, beta_forward=0.15, beta_back=0.0
    )


@pytest.fixture(scope="module")
def result(tmp_path_factory):
    config = ExperimentConfig(
        min_train_seasons=1,
        bootstrap_replications=50,
        seed=0,
        mlflow_uri=f"sqlite:///{tmp_path_factory.mktemp('mlflow')}/mlflow.db",
        reports_dir=tmp_path_factory.mktemp("experiments"),
    )
    started = time.monotonic()
    out = run_experiment(lambda: GBMRiskModel(seed=0), _df(), config)
    assert time.monotonic() - started < 300, "run M3 trop lent"
    return out


def test_run_completes_with_folds(result) -> None:
    assert len(result.folds) == 1  # 3 saisons -> 1 fold, comme le réel
    assert result.aggregated.n > 0
    assert result.aggregated.log_loss > 0
    assert result.report_path.exists()


def test_report_has_shap_ale_and_curves_no_player_keys(result) -> None:
    text = result.report_path.read_text(encoding="utf-8")
    for section in ("SHAP", "ALE consecutive_matches", "Courbes h(N)"):
        assert section in text
    assert "player_key" not in text
    assert "Association" in text


def test_shap_finds_simulated_interaction() -> None:
    import shap  # noqa: PLC0415

    df = _df(seasons=2)
    train = df.filter(pl.col("season_id") == "2020-2021")
    valid = df.filter(pl.col("season_id") == "2021-2022")
    model = GBMRiskModel(seed=0).fit(train, valid)
    sample = model._valid_X.iloc[:2000]  # type: ignore[union-attr]
    values = shap.TreeExplainer(model.clf_).shap_values(_shap_numeric(sample))  # type: ignore[union-attr]
    if isinstance(values, list):  # anciennes versions : liste par classe
        values = values[1]
    mean_abs = np.abs(values).mean(axis=0)
    by_feature = dict(zip(sample.columns, mean_abs, strict=True))
    # consecutive_matches porte l'interaction simulée ; is_home n'a aucun effet dans le DGP.
    assert by_feature["consecutive_matches"] > 2 * by_feature["is_home"]
    assert by_feature["consecutive_matches"] > 0
