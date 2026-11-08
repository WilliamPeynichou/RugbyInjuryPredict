"""Priors épidémiologiques centralisés (F19).

Toutes les constantes de la littérature vivent ici et nulle part ailleurs dans
`src/rugby_risk/modeling/` (critère grep testé dans `tests/unit/modeling/test_priors.py`).
Source unique : `docs/02-science-priors.md` §1. Unités : blessures pour 1000 heures
d'exposition sauf mention contraire.
"""

import math
from typing import Final

PRIORS_VERSION: Final = "1.1.0"  # 1.1 : priors M2 (F22)

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

# --- Charge (Williams 2017) --------------------------------------------------------
WILLIAMS_2017_LOAD_IRR: Final = 1.14  # par +3,2 FGE (matchs complets) sur 30 jours
WILLIAMS_2017_LOAD_FGE: Final = 3.2
FULL_GAME_MINUTES: Final = 80.0

# --- Priors du modèle hiérarchique M2 (docs/06 §2, F22) ----------------------------
# Échelle cloglog, hazard par match complet (offset log(minutes/80)).
M2_BASE_MATCH_PROB: Final = 0.07  # P(blessure) par match complet, centre du prior (4-12 %)
M2_INTERCEPT_SD: Final = 0.5
M2_SIGMA_POSITION_SD: Final = 0.3  # sigma_unit, sigma_group, sigma_code ~ HalfNormal(0,3)
M2_SLOPE_SD: Final = 0.2  # pente consecutive_matches standardisée, par groupe
M2_SIGMA_PLAYER_SD: Final = 0.5  # fragilité joueur
M2_SIGMA_TEAM_SD: Final = 0.3  # équipe-saison
M2_LOAD_SD: Final = 0.15  # pente de charge, par +3,2 FGE / 30 j
M2_FIXED_SD: Final = 0.5  # autres effets fixes (standardisés / binaires), faiblement informatif
# Prior predictive check : incidence simulée par poste (/1000 h, docs/06 §2).
M2_PRIOR_INCIDENCE_BAND: Final = (30.0, 150.0)


def m2_intercept_mu() -> float:
    """cloglog(0,07) = log(-log(1 - 0,07)) ≈ -2,62 (docs/06 §2)."""
    return math.log(-math.log(1.0 - M2_BASE_MATCH_PROB))


def m2_load_prior(min_28d_std: float) -> tuple[float, float]:
    """Prior (mu, sd) of the standardized `min_28d` slope from Williams 2017.

    log(1,14) per +3,2 FGE = +256 minutes; the design divides min_28d by its training
    standard deviation, so both mu and sd scale by std / 256.
    """
    if min_28d_std <= 0:
        raise ValueError(f"Écart-type min_28d non positif : {min_28d_std}")
    scale = min_28d_std / (WILLIAMS_2017_LOAD_FGE * FULL_GAME_MINUTES)
    return math.log(WILLIAMS_2017_LOAD_IRR) * scale, M2_LOAD_SD * scale


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
