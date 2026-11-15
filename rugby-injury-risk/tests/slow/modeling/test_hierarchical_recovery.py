"""F22 (slow) : le modèle hiérarchique M2 retrouve les effets par poste du DGP (>= 8/9 IC90)."""

import numpy as np
import pytest

from rugby_risk.modeling.hierarchical import (
    FAST_SAMPLER,
    HierarchicalHazardModel,
)
from tests.hazard_factory import TRUE_POSITION_EFFECTS, hierarchical_frame

pytestmark = pytest.mark.slow

CI_LEVELS = (0.05, 0.95)
MIN_COVERED = 8


@pytest.fixture(scope="module")
def fitted() -> HierarchicalHazardModel:
    """DGP hiérarchique connu (TRUE_POSITION_EFFECTS) : fit --fast, seed fixe."""
    train = hierarchical_frame(players=400, seasons=2, matches=26, seed=5)
    model = HierarchicalHazardModel(sampler=FAST_SAMPLER, ipw=False, seed=5)
    return model.fit(train)


def test_position_effects_recovered(fitted: HierarchicalHazardModel) -> None:
    index = fitted.index_
    assert index is not None
    draws = fitted.posterior_.draws["position_effect"]  # (draws, codes)
    covered = 0
    for i, code in enumerate(index.codes):
        lo, hi = np.quantile(draws[:, i], CI_LEVELS)
        if lo <= TRUE_POSITION_EFFECTS[code] <= hi:
            covered += 1
    assert covered >= MIN_COVERED, {
        code: (float(np.quantile(draws[:, i], 0.05)), float(np.quantile(draws[:, i], 0.95)))
        for i, code in enumerate(index.codes)
    }


def test_fit_reports_diagnostics(fitted: HierarchicalHazardModel) -> None:
    """Mode --fast : seuils relâchés (docs/06 §6 vaut pour le run de référence complet).

    Un run fast avec diagnostics dégradés reste marqué `failed` (non publiable) mais doit
    être rapporté : on borne ici les écarts pour détecter une dérive du sampler.
    """
    assert fitted.diagnostics_ is not None
    assert fitted.diagnostics_.r_hat_max < 1.05
    assert fitted.diagnostics_.divergences <= 10
    assert fitted.prior_check_ok is True
    tables = fitted.report_tables()
    assert "M2 : diagnostics MCMC" in tables
    assert "M2 : effets (moyenne postérieure, IC90 crédible)" in tables
