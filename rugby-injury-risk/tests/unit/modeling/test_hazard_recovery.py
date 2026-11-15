"""F20: M1 recovers a simulated load effect (log-HR 0.05 per match forwards, 0 backs)."""

import numpy as np
import polars as pl
import pytest

from rugby_risk.modeling.design import DesignSpec
from rugby_risk.modeling.hazard import DiscreteHazardModel
from tests.hazard_factory import hazard_frame

TRUE_FORWARD = 0.05
TRUE_BACK = 0.0
BY_UNIT = DesignSpec(
    categorical=("unit",),
    splines=(),
    linear=("consecutive_matches",),
    interactions=(("unit", "consecutive_matches"),),
    standardize=False,
)


@pytest.fixture(scope="module")
def model() -> DiscreteHazardModel:
    df = hazard_frame(players=900, seasons=3, beta_forward=TRUE_FORWARD, beta_back=TRUE_BACK)
    return DiscreteHazardModel(link="cloglog", spec=BY_UNIT, curve_replications=0).fit(df)


def _row(coefs: pl.DataFrame, term: str) -> dict[str, float]:
    return coefs.filter(pl.col("term") == term).row(0, named=True)


def test_back_slope_recovered(model: DiscreteHazardModel) -> None:
    # Référence = « back » (premier niveau trié) : pente principale = pente des arrières.
    back = _row(model.coefficients(), "consecutive_matches")
    assert back["low"] <= TRUE_BACK <= back["high"]


def test_forward_minus_back_recovered(model: DiscreteHazardModel) -> None:
    diff = _row(model.coefficients(), "consecutive_matches__x__unit_forward")
    assert diff["low"] <= TRUE_FORWARD - TRUE_BACK <= diff["high"]
    assert diff["low"] > 0, "effet avants détecté (IC95 % au-dessus de 0)"


def test_predictions_are_probabilities(model: DiscreteHazardModel) -> None:
    p = model.predict_proba(hazard_frame(players=20, seasons=1, seed=9))
    assert np.all((p > 0) & (p < 1))
    assert model.params()["converged"] is True


def test_unknown_link_rejected() -> None:
    with pytest.raises(ValueError, match="Lien inconnu"):
        DiscreteHazardModel(link="probit")
