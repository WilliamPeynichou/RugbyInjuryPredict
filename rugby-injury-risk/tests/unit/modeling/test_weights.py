"""F21: stabilized IPW weights — stabilization, truncation, ESS (unit, pure function)."""

import numpy as np
import pytest

from rugby_risk.modeling.selection import stabilized_weights

PI = np.array([0.9, 0.5, 0.2, 0.95, 0.6, 0.4, 0.85, 0.55, 0.3, 0.7])
POS = np.array(["a", "a", "b", "a", "b", "b", "a", "b", "a", "b"])
RATES = {"a": 0.8, "b": 0.6}


def test_stabilized_numerator_comes_from_position_rates() -> None:
    w, diag = stabilized_weights(PI, POS, stabilize=True, position_rates=RATES, truncate=(0.0, 1.0))
    expected = np.array([RATES[p] for p in POS]) / PI
    np.testing.assert_allclose(w, expected)
    assert diag.stabilized is True
    assert diag.ipw_enabled is False  # renseigné par le gate de calibration (appelant)


def test_unstabilized_is_plain_inverse() -> None:
    w, diag = stabilized_weights(PI, POS, stabilize=False, position_rates=None, truncate=(0.0, 1.0))
    np.testing.assert_allclose(w, 1 / PI)
    assert diag.stabilized is False


def test_truncation_bounds_respected() -> None:
    w, diag = stabilized_weights(PI, POS, stabilize=False, position_rates=None, truncate=(0.1, 0.9))
    assert w.min() >= diag.truncate_lo
    assert w.max() <= diag.truncate_hi
    # La troncature aux quantiles 10/90 de w non tronqué (1/pi) : borne basse = q10(1/pi).
    assert diag.truncate_lo == pytest.approx(float(np.quantile(1 / PI, 0.1)))
    assert diag.truncate_hi == pytest.approx(float(np.quantile(1 / PI, 0.9)))


def test_ess_between_1_and_n() -> None:
    _w, diag = stabilized_weights(
        PI, POS, stabilize=True, position_rates=RATES, truncate=(0.0, 1.0)
    )
    assert 1 <= diag.ess <= diag.n
    # Poids constants -> ESS = n ; poids très hétérogènes -> ESS nettement < n.
    _, diag_const = stabilized_weights(
        np.full(10, 0.8), POS, stabilize=False, position_rates=None, truncate=(0.0, 1.0)
    )
    assert diag_const.ess == pytest.approx(10.0)
    assert diag.ess_ratio < 1.0


def test_stabilization_requires_rates() -> None:
    with pytest.raises(ValueError, match="position_rates"):
        stabilized_weights(PI, POS, stabilize=True, position_rates=None, truncate=(0.0, 1.0))


def test_unknown_position_rejected() -> None:
    with pytest.raises(ValueError, match="Poste absent"):
        stabilized_weights(
            PI, np.array(["z"] * 10), stabilize=True, position_rates=RATES, truncate=(0.0, 1.0)
        )
