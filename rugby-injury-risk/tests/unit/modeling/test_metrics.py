import numpy as np
import pytest

from rugby_risk.modeling.metrics import calibration, calibration_curve, evaluate

pytestmark = pytest.mark.unit


def test_constant_prediction_brier_is_p_1_minus_p_plus_bias_sq():
    n = 4000
    y = np.array([0, 1] * (n // 2), dtype=float)
    m = evaluate(y, np.full(n, 0.5))
    assert m.brier == pytest.approx(0.25, abs=1e-3)
    # Prévalence 0.5, prédiction constante 0.3 : biais^2 + p(1-p)
    m2 = evaluate(y, np.full(n, 0.3))
    assert m2.brier == pytest.approx(0.3**2 * 0.5 + 0.7**2 * 0.5, abs=1e-3)


def test_perfectly_calibrated_model_slope_near_one():
    rng = np.random.default_rng(1)  # seed 0 : fluctuation d'échantillonnage à 2 sigma
    n = 20000
    p = rng.uniform(0.02, 0.2, n)
    y = (rng.uniform(size=n) < p).astype(float)
    slope, intercept = calibration(y, np.log(p / (1 - p)))
    assert slope == pytest.approx(1.0, abs=0.1)
    assert intercept == pytest.approx(0.0, abs=0.1)


def test_brier_skill_positive_when_better_than_reference():
    n = 4000
    rng = np.random.default_rng(1)
    p = rng.uniform(0.05, 0.15, n)
    y = (rng.uniform(size=n) < p).astype(float)
    good = evaluate(y, p, p_reference=np.full(n, y.mean()))
    assert good.brier_skill is not None and good.brier_skill > 0
    bad = evaluate(y, np.full(n, y.mean()), p_reference=p)
    assert bad.brier_skill is not None and bad.brier_skill < 0


def test_auc_alert_above_threshold():
    n = 2000
    rng = np.random.default_rng(2)
    signal = rng.normal(size=n)
    y = (signal > 0).astype(float)
    m = evaluate(y, 1 / (1 + np.exp(-4 * signal)))
    assert m.auc_roc > 0.75
    assert any("fuite" in a or "AUC" in a or "auc" in a for a in m.alerts)


def test_calibration_curve_bins_sum_to_n():
    rng = np.random.default_rng(3)
    n = 5000
    p = rng.uniform(0.01, 0.3, n)
    y = (rng.uniform(size=n) < p).astype(float)
    curve = calibration_curve(y, p, n_bins=10)
    assert curve["n"].sum() == n
    assert len(curve["p_pred"]) == len(curve["p_obs"]) == len(curve["bin"])


def test_evaluate_handles_single_class():
    y = np.zeros(100)
    m = evaluate(y, np.full(100, 0.05))
    assert m.n == 100 and m.prevalence == 0.0
