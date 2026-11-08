"""Priors épidémiologiques centralisés (F19).

Toutes les constantes de la littérature vivent ici et nulle part ailleurs dans
`src/rugby_risk/modeling/` (critère grep testé dans `tests/unit/modeling/test_priors.py`).
Source unique : `docs/02-science-priors.md` §1. Unités : blessures pour 1000 heures
d'exposition sauf mention contraire.
"""

import math
from typing import Final

PRIORS_VERSION: Final = "1.0.0"

# --- Incidence en match (PRISP) -------------------------------------------------
INCIDENCE_PREMIERSHIP_2022_23: Final = 76.0  # /1000 h
INCIDENCE_PREMIERSHIP_MEAN_2002_22: Final = 86.0  # /1000 h
INJURIES_PER_TEAM_MATCH: Final = 1.5

# --- Gravité et burden (PRISP 2022-23) ------------------------------------------
SEVERITY_MEAN_DAYS: Final = 38.0
SEVERITY_MEDIAN_DAYS: Final = 17.0
SEVERITY_MEDIAN_DAYS_2002_22: Final = 10.0
BURDEN_DAYS_PER_1000H: Final = 2879.0

# --- Commotion (PRISP 2022-23 ; Chéradame et al. 2021 pour le Top 14) ------------
CONCUSSION_INCIDENCE_MATCH: Final = 18.4  # /1000 h
CONCUSSION_SHARE_OF_INJURIES: Final = 0.24
CONCUSSION_MEAN_DAYS: Final = 18.0
CONCUSSION_TOP14_2014_18: Final = 10.4  # /1000 h, IC 90 % 9.3-11.5
CONCUSSION_TOP14_2014_18_CI90: Final = (9.3, 11.5)
CONCUSSION_TOP14_SCRUM_HALF: Final = 16.1  # /1000 h

# --- Entraînement, mécanisme, surface --------------------------------------------
INCIDENCE_TRAINING: Final = 3.2  # /1000 h
TACKLE_SHARE_OF_MATCH_INJURIES: Final = 0.50
INCIDENCE_SYNTHETIC_VS_NATURAL: Final = (84.0, 81.0)  # /1000 h, 10 saisons
SEVERITY_DELTA_SYNTHETIC_DAYS: Final = 6.0  # 39 vs 33 j

# --- Références par contexte ------------------------------------------------------
RWC_2015_INCIDENCE: Final = 90.1  # /1000 h
RWC_2015_INCIDENCE_BACKS: Final = 100.4
RWC_2015_INCIDENCE_FORWARDS: Final = 81.1
RWC_2015_SEVERITY_MEAN_DAYS: Final = 29.8
HOOKER_PREMIERSHIP_2002_04: Final = 114.0  # /1000 h, poste le plus exposé
FORWARDS_VS_BACKS_IRR_META_2025: Final = 1.03  # IC 95 % 1.00-1.06
FORWARDS_VS_BACKS_IRR_META_2025_CI95: Final = (1.00, 1.06)
POST_CONCUSSION_RISK_INCREASE: Final = 0.60  # +60 % de risque ultérieur (Cross 2016)


def rate_to_match_prob(rate_per_1000h: float, minutes: float) -> float:
    """P(au moins une blessure) pour un taux constant et une exposition en minutes.

    Processus de Poisson : P = 1 - exp(-lambda * E) avec lambda en blessures/heure.
    rate_per_1000h=76 et minutes=80 donne ~0,096 ; 114 et 80 donne ~0,141
    (docs/02-science-priors.md §2).
    """
    if rate_per_1000h < 0:
        raise ValueError(f"Taux négatif: {rate_per_1000h}")
    if minutes < 0:
        raise ValueError(f"Minutes négatives: {minutes}")
    lam = rate_per_1000h / 1000.0 * (minutes / 60.0)
    return float(1.0 - math.exp(-lam))


def expected_base_rate_band() -> tuple[float, float]:
    """Bande attendue pour le taux de base reconstruit (sous-déclaration), /1000 h."""
    return (50.0, 80.0)
