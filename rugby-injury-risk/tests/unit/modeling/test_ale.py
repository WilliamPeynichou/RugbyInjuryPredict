"""F23 : ALE d'une fonction connue — forme et centrage."""

import numpy as np
import pytest

from rugby_risk.modeling.ale import ale_1d

pytestmark = pytest.mark.unit


def test_ale_recovers_shape_of_square() -> None:
    rng = np.random.default_rng(0)
    matrix = rng.uniform(0, 1, size=(4000, 3))
    j = 1

    def predict(rows: np.ndarray) -> np.ndarray:
        return rows[:, j] ** 2

    centers, effects = ale_1d(predict, matrix, j, n_bins=10)
    ok = np.isfinite(centers)
    centers, effects = centers[ok], effects[ok]
    assert len(centers) >= 8
    # x² est croissante sur (0,1) : l'ALE croît avec le centre de bin.
    assert np.all(np.diff(effects) > 0)
    assert np.all(np.diff(centers) > 0)
    # Centré sur la distribution des lignes (moyenne pondérée nulle, à tolérance près).
    assert abs(np.mean(effects)) < 0.05


def test_ale_rejects_bad_matrix() -> None:
    with pytest.raises(ValueError, match="matrice"):
        ale_1d(lambda m: m[:, 0], np.zeros(10), 0)
