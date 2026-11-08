"""F19 : conversion taux -> probabilité par match, et centralisation des constantes."""

import math
from pathlib import Path

import pytest

from rugby_risk.modeling import priors
from rugby_risk.modeling.priors import expected_base_rate_band, rate_to_match_prob

MODELING_DIR = Path(priors.__file__).parent


def test_rate_to_match_prob_premiership_mean() -> None:
    assert rate_to_match_prob(76, 80) == pytest.approx(0.096, abs=0.002)


def test_rate_to_match_prob_hooker() -> None:
    assert rate_to_match_prob(114, 80) == pytest.approx(0.14, abs=0.002)


def test_rate_to_match_prob_zero_exposure() -> None:
    assert rate_to_match_prob(76, 0) == 0.0
    assert rate_to_match_prob(0, 80) == 0.0


def test_rate_to_match_prob_is_poisson_cdf() -> None:
    # Cohérence avec la formule fermée 1 - exp(-lambda * E).
    assert rate_to_match_prob(40, 30) == pytest.approx(1 - math.exp(-40 / 1000 * 0.5))


def test_rate_to_match_prob_rejects_negative() -> None:
    with pytest.raises(ValueError):
        rate_to_match_prob(-1, 80)
    with pytest.raises(ValueError):
        rate_to_match_prob(76, -1)


def test_epidemiological_constants_not_duplicated() -> None:
    """Aucune constante de docs/02 §1 hors priors.py (critère d'acceptation F19)."""
    forbidden = ["76.0", "114.0", "18.4"]
    for path in MODELING_DIR.glob("*.py"):
        if path.name == "priors.py":
            continue
        text = path.read_text(encoding="utf-8")
        for token in forbidden:
            assert token not in text, f"Constante épidémio `{token}` trouvée dans {path.name}"


def test_priors_version_exists() -> None:
    assert priors.PRIORS_VERSION.count(".") == 2
    lo, hi = expected_base_rate_band()
    assert 0 < lo < hi


def test_m2_intercept_prior_matches_docs() -> None:
    """docs/06 §2 : log(-log(1 - 0,07)) ≈ -2,62, ±0,5 couvre ~4-12 % par match."""
    mu = priors.m2_intercept_mu()
    assert mu == pytest.approx(-2.62, abs=0.01)
    lo = 1 - math.exp(-math.exp(mu - priors.M2_INTERCEPT_SD))
    hi = 1 - math.exp(-math.exp(mu + priors.M2_INTERCEPT_SD))
    assert 0.04 < lo < 0.05
    assert 0.10 < hi < 0.12


def test_m2_load_prior_scales_with_std() -> None:
    """256 minutes (3,2 FGE) d'écart-type -> exactement log(1,14) et 0,15."""
    mu, sd = priors.m2_load_prior(256.0)
    assert mu == pytest.approx(math.log(1.14))
    assert sd == pytest.approx(0.15)
    mu_half, _ = priors.m2_load_prior(128.0)
    assert mu_half == pytest.approx(mu / 2)
    with pytest.raises(ValueError):
        priors.m2_load_prior(0.0)
