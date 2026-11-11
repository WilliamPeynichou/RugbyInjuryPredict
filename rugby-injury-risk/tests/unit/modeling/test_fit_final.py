"""F30 : l'ajustement final n'utilise jamais la saison de test finale gelée."""

import polars as pl
import pytest

from rugby_risk.modeling.null import ConstantModel
from rugby_risk.modeling.runner import ExperimentConfig, fit_final
from rugby_risk.modeling.validation import FINAL_TEST_SEASON
from tests.hazard_factory import hazard_frame

pytestmark = pytest.mark.unit


class _Recorder(ConstantModel):
    seen: pl.DataFrame | None = None

    def fit(self, train: pl.DataFrame, valid: pl.DataFrame | None = None) -> "_Recorder":
        type(self).seen = train
        return self


def test_final_test_season_excluded(tmp_path) -> None:
    df = hazard_frame(players=30, seasons=6, matches=6, seed=1)
    assert FINAL_TEST_SEASON in df["season_id"].to_list()
    config = ExperimentConfig(
        min_label_followup=1,
        reports_dir=tmp_path / "experiments",
        mlflow_uri=f"sqlite:///{tmp_path}/mlflow.db",
    )
    final = fit_final(_Recorder, df, config)
    assert FINAL_TEST_SEASON not in final.seasons
    assert _Recorder.seen is not None
    assert FINAL_TEST_SEASON not in _Recorder.seen["season_id"].to_list()
    assert _Recorder.seen["played"].all()
    assert final.dataset_version == "synthetic"
    assert len(final.seasons) == 5
