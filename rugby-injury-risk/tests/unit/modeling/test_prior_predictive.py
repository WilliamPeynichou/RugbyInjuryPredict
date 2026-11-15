"""F22 : prior predictive check M2 (docs/06 §2) — incidences simulées par poste dans la bande."""

import polars as pl
import pytest

from rugby_risk.modeling.hierarchical import HierarchicalHazardModel, SamplerConfig
from rugby_risk.modeling.priors import M2_PRIOR_INCIDENCE_BAND
from tests.hazard_factory import hierarchical_frame

pytestmark = pytest.mark.unit

QUANTILE_COLS = ("q05", "q25", "median", "q75", "q95")


@pytest.fixture(scope="module")
def prior_table() -> pl.DataFrame:
    """Échantillonnage prior uniquement (pas de NUTS) : rapide et déterministe (seed fixe)."""
    train = hierarchical_frame(players=300, seasons=1, matches=20, seed=1)
    model = HierarchicalHazardModel(sampler=SamplerConfig(prior_draws=400), ipw=False, seed=1)
    return model.prior_incidence(train)


def test_all_positions_present(prior_table: pl.DataFrame) -> None:
    assert prior_table.height == 9  # les 9 postes du DGP hiérarchique
    assert prior_table["position_code"].n_unique() == 9
    for col in (*QUANTILE_COLS, "in_band"):
        assert col in prior_table.columns


def test_quantiles_ordered(prior_table: pl.DataFrame) -> None:
    q05, q25, median, q75, q95 = (prior_table[c].to_numpy() for c in QUANTILE_COLS)
    assert (q05 <= q25).all() and (q25 <= median).all()
    assert (median <= q75).all() and (q75 <= q95).all()


def test_medians_in_expected_band(prior_table: pl.DataFrame) -> None:
    """Toutes les médians d'incidence simulée (/1000 h) doivent tomber dans la bande du prior."""
    lo, hi = M2_PRIOR_INCIDENCE_BAND
    medians = prior_table["median"].to_list()
    assert all(lo <= m <= hi for m in medians), medians
    assert prior_table["in_band"].all()
