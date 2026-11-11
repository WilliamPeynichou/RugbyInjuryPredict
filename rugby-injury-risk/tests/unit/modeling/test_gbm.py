"""F23 : M3 LightGBM calibré — isotone sur validation uniquement, courbes, garde-fous."""

import numpy as np
import polars as pl
import pytest

from rugby_risk.modeling.curves import hazard_curve
from rugby_risk.modeling.gbm import EXPOSURE_FEATURE, GBMRiskModel
from tests.hazard_factory import POSITIONS, hazard_frame

pytestmark = pytest.mark.unit


@pytest.fixture(scope="module")
def split() -> tuple[pl.DataFrame, pl.DataFrame]:
    df = hazard_frame(players=150, seasons=2, matches=10, seed=2)
    train = df.filter(pl.col("season_id") == "2020-2021")
    valid = df.filter(pl.col("season_id") == "2021-2022")
    return train, valid


@pytest.fixture(scope="module")
def model(split) -> GBMRiskModel:
    return GBMRiskModel(seed=0).fit(split[0], split[1])


def test_predict_proba_is_calibrated_probability(model, split) -> None:
    p = model.predict_proba(split[1])
    assert p.shape == (len(split[1]),)
    assert ((p > 0) & (p < 1)).all()
    assert np.isfinite(p).all()


def test_isotone_fit_on_validation_only(model, split) -> None:
    # La calibration est apprise sur les prédictions de la validation, jamais du train/test.
    assert len(model.iso_.X_thresholds_) <= len(split[1])  # type: ignore[union-attr]
    assert len(model.iso_.X_thresholds_) > 1  # type: ignore[union-attr]
    # Le modèle brut et la probabilité calibrée diffèrent (isotone non triviale).
    raw = model.clf_.predict_proba(model._frame(split[1]))[:, 1]  # type: ignore[union-attr]
    assert not np.allclose(raw, model.predict_proba(split[1]))


def test_curves_use_scenario_profiles(model) -> None:
    codes = {p[0] for p in POSITIONS}
    assert set(model.profiles_) == codes
    h = hazard_curve(model, "PROP", (0, 3, 6))
    assert h.shape == (3,)
    assert ((h > 0) & (h < 1)).all()
    with pytest.raises(KeyError):
        hazard_curve(model, "PROP", (0,), scenario="unknown_scenario")


def test_fit_requires_validation(split) -> None:
    with pytest.raises(ValueError, match="validation"):
        GBMRiskModel().fit(split[0])


def test_predict_requires_columns(model, split) -> None:
    dropped = split[1].drop("min_28d")
    with pytest.raises(ValueError, match="Colonnes absentes"):
        model.predict_proba(dropped)


def test_params_report_grid_and_exposure(model) -> None:
    params = model.params()
    assert params["grid_size"] == 8
    assert EXPOSURE_FEATURE in params["features"]
    assert params["calibration"].startswith("isotone")
    assert model.best_params_["max_iter"] >= 300


def test_monotone_constraints_reported(split) -> None:
    model = GBMRiskModel(seed=0, monotone={"days_since_last_match": -1}).fit(*split)
    assert model.params()["monotone"] == {"days_since_last_match": -1}
    plain = GBMRiskModel(seed=0).fit(*split)
    assert plain.params()["monotone"] is None


def test_exposure_never_decreases_risk(model, split) -> None:
    # Offset arbre : un joueur remplaçé tôt (blessé) ne doit pas faire « peu de minutes = risque ».
    rows = split[1].head(200)
    probs = [
        model.predict_proba(rows.with_columns(pl.lit(float(m)).alias("minutes_played")))
        for m in (10, 40, 80)
    ]
    assert (np.diff(np.vstack(probs), axis=0) >= -1e-12).all()


def test_exposure_constraint_cannot_be_disabled() -> None:
    with pytest.raises(ValueError, match="offset"):
        GBMRiskModel(monotone={EXPOSURE_FEATURE: 0})


def test_missing_indicators_never_retained(split) -> None:
    # Indicateurs de couverture : écartés même quand ils varient (EXCLUDED_SUFFIXES).
    train, valid = (
        frame.with_columns((pl.col("min_28d") > 0).cast(pl.Int8).alias("age_missing"))
        for frame in split
    )
    model = GBMRiskModel(seed=0).fit(train, valid)
    assert not [c for c in model.features_ if c.endswith("_missing")]
    assert "age_missing" in model.excluded_
    assert "age_missing" in model.params()["excluded_features"].split(",")
    assert "age_missing" not in model.params()["features"].split(",")


def test_excluded_features_reported(model) -> None:
    # Textes et redondances (EXCLUDED_FEATURES) : listés, jamais utilisés par les arbres.
    assert set(model.excluded_) <= {"position_group", "unit", "competition_code", "surface"}
    assert "position_group" in model.params()["excluded_features"]
