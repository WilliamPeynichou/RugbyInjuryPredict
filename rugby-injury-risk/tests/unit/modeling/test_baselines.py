"""F19 : baselines M0 — taux par poste estimés correctement, lissage gamma-Poisson."""

import numpy as np
import polars as pl
import pytest

from rugby_risk.modeling.baselines import GlobalRateModel, PositionRateModel
from rugby_risk.modeling.priors import rate_to_match_prob

TRUE_RATES = {  # blessures / 1000 h
    "PILIER": 90.0,
    "TALONNEUR": 114.0,
    "DEMI_MELEE": 70.0,
    "AILIER": 80.0,
}
GROUPS = {"PILIER": "AVANT", "TALONNEUR": "AVANT", "DEMI_MELEE": "ARRIERE", "AILIER": "ARRIERE"}


def _simulate(seed: int = 7, rows_per_pos: int = 400) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    rows = []
    for code, rate in TRUE_RATES.items():
        minutes = rng.integers(10, 81, size=rows_per_pos).astype(float)
        prob = 1.0 - np.exp(-rate / 1000.0 * minutes / 60.0)
        y = rng.binomial(1, prob)
        for m, t in zip(minutes, y, strict=True):
            rows.append(
                {
                    "position_code": code,
                    "position_group": GROUPS[code],
                    "minutes_played": float(m),
                    "y_injury": int(t),
                }
            )
    return pl.DataFrame(rows)


@pytest.fixture(scope="module")
def train() -> pl.DataFrame:
    return _simulate()


def test_position_rates_within_ci(train) -> None:
    model = PositionRateModel(smoothing_hours=0.0).fit(train)
    for code, true_rate in TRUE_RATES.items():
        est = model.rates_.by_code[code] * 1000  # type: ignore[union-attr]
        hours, injuries = model.rates_.exposure[code]  # type: ignore[union-attr]
        se = np.sqrt(injuries) / hours * 1000
        assert abs(est - true_rate) < 2 * se, f"{code}: {est:.1f} vs vrai {true_rate}"


def test_smoothing_pulls_low_exposure_toward_group(train) -> None:
    # Un poste quasi sans exposition : le brut est instable, le lissé colle au groupe.
    rare = pl.DataFrame(
        {
            "position_code": ["TALONNEUR_BIS"] * 3,
            "position_group": ["AVANT"] * 3,
            "minutes_played": [15.0, 20.0, 10.0],  # < 1 h au total, 0 blessure
            "y_injury": [0, 0, 0],
        }
    )
    df = pl.concat([train, rare])
    raw = PositionRateModel(smoothing_hours=0.0).fit(df)
    smooth = PositionRateModel(smoothing_hours=200.0).fit(df)
    group_rate = smooth.rates_.by_group["AVANT"]  # type: ignore[union-attr]
    est_raw = raw.rates_.by_code["TALONNEUR_BIS"]  # type: ignore[union-attr]
    est_smooth = smooth.rates_.by_code["TALONNEUR_BIS"]  # type: ignore[union-attr]
    assert abs(est_smooth - group_rate) < abs(est_raw - group_rate)
    # Avec 0 blessure et quasi pas d'heures, le lissé reste positif mais borné par le parent.
    assert 0 < est_smooth < group_rate * 1.05


def test_prediction_matches_closed_form(train) -> None:
    model = PositionRateModel(smoothing_hours=0.0).fit(train)
    df = pl.DataFrame(
        {
            "position_code": ["PILIER", "PILIER"],
            "position_group": ["AVANT", "AVANT"],
            "minutes_played": [80.0, 40.0],
        }
    )
    p = model.predict_proba(df)
    est = model.rates_.by_code["PILIER"] * 1000  # type: ignore[union-attr]
    assert p[0] == pytest.approx(rate_to_match_prob(est, 80), rel=1e-6)
    assert p[0] > p[1]  # plus d'exposition = plus de risque
    assert p[1] == pytest.approx(rate_to_match_prob(est, 40), rel=1e-6)


def test_unknown_position_falls_back_to_group(train) -> None:
    model = PositionRateModel(smoothing_hours=0.0).fit(train)
    df = pl.DataFrame(
        {
            "position_code": ["NOUVEAU_POSTE"],
            "position_group": ["ARRIERE"],
            "minutes_played": [80.0],
        }
    )
    p = model.predict_proba(df)
    assert p[0] == pytest.approx(
        rate_to_match_prob(model.rates_.by_group["ARRIERE"] * 1000, 80), rel=1e-6
    )  # type: ignore[union-attr]


def test_global_model_constant_per_exposure(train) -> None:
    model = GlobalRateModel().fit(train)
    df = pl.DataFrame({"minutes_played": [80.0, 40.0, 0.0]})
    p = model.predict_proba(df)
    assert p[0] > p[1] > p[2] == 0.0
    # Le taux global se situe entre le plus faible et le plus fort des postes.
    rate = model.rates_.global_rate * 1000  # type: ignore[union-attr]
    assert min(TRUE_RATES.values()) < rate < max(TRUE_RATES.values())


def test_unfitted_predict_raises() -> None:
    with pytest.raises(RuntimeError):
        PositionRateModel().predict_proba(pl.DataFrame({"minutes_played": [80.0]}))
    with pytest.raises(RuntimeError):
        GlobalRateModel().predict_proba(pl.DataFrame({"minutes_played": [80.0]}))


def test_empty_exposition_raises() -> None:
    df = pl.DataFrame(
        {
            "position_code": ["PILIER"],
            "position_group": ["AVANT"],
            "minutes_played": [0.0],
            "y_injury": [0],
        }
    )
    with pytest.raises(ValueError):
        PositionRateModel().fit(df)


def test_nan_minutes_raise_instead_of_silent_nan() -> None:
    """Un trou d'exposition ne doit jamais produire une proba NaN silencieuse."""
    df = pl.DataFrame(
        {
            "position_code": ["PILIER", "PILIER", "PILIER"],
            "position_group": ["AVANT", "AVANT", "AVANT"],
            "minutes_played": [80.0, 80.0, None],
            "y_injury": [0, 1, 0],
        }
    )
    model = PositionRateModel()
    with pytest.raises(ValueError, match="minutes_played"):
        model.fit(df)
    model.fit(df.drop_nulls(subset=["minutes_played"]))
    with pytest.raises(ValueError, match="minutes_played"):
        model.predict_proba(df)


def test_report_tables_have_priors_reference(train) -> None:
    model = PositionRateModel().fit(train)
    tables = model.report_tables()
    assert "Taux M0 par poste" in tables
    assert "IC95" in tables["Taux M0 par poste"]
    assert "Premiership" in tables["Taux M0 par poste"]  # comparaison priors
