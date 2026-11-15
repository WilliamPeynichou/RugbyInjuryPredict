"""F21: simulation du biais du survivant — M1 naïf biaisé, M1w rejoint la cible éligible.

DGP (tests/hazard_factory.py::selection_frame) : X = séquence et Z = signal de fatigue
indépendants dans la population éligible ; `played` est un collider commun (le staff aligne
les joueurs frais et fait tourner après les longues séquences). Le M1 ajusté sur les lignes
jouées sous-estime le coefficient de charge de la population éligible ; l'IPW (π̂(X, Z),
gate de calibration ouvert) restaure cette population. Cible = M1 ajusté sur TOUTES les
lignes éligibles (y est généré pour toutes, indépendamment de played).

Sélection forte (sel_a/sel_b/sel_c) + troncature 0,1-99,9 : la troncature 1-99 du défaut
docs/06 écrête la queue de poids qui porte la correction (sensibilité documentée dans le
journal F21 ; variantes de troncature enregistrées dans le registry).
"""

import polars as pl
import pytest

from rugby_risk.modeling.design import DesignSpec
from rugby_risk.modeling.hazard import DiscreteHazardModel
from rugby_risk.modeling.selection import SelectionModel, WeightedHazardModel
from tests.hazard_factory import selection_frame

# Spec volontairement simple : le DGP est linéaire en consecutive_matches.
SPEC = DesignSpec(
    categorical=(),
    splines=(),
    linear=("consecutive_matches",),
    standardize=False,
)


@pytest.fixture(scope="module")
def fitted() -> tuple[DiscreteHazardModel, DiscreteHazardModel, WeightedHazardModel]:
    df = selection_frame(seed=0, sel_a=3.4, sel_b=0.30, sel_c=1.2)
    played = df.filter(pl.col("played"))
    naive = DiscreteHazardModel(link="cloglog", spec=SPEC, curve_replications=0).fit(played)
    # Cible : même modèle (même spécification imparfaite y ~ X seul) sur la population
    # éligible entière ; minutes uniformes 80 pour que l'offset soit défini partout.
    full = df.with_columns(pl.lit(80, dtype=pl.Int32).alias("minutes_played"))
    target = DiscreteHazardModel(link="cloglog", spec=SPEC, curve_replications=0).fit(full)
    weighted = WeightedHazardModel(curve_replications=0, spec=SPEC, truncate=(0.001, 0.999)).fit(
        played, eligible=df
    )
    return naive, target, weighted


def _load_coef(model: DiscreteHazardModel) -> float:
    coefs = model.coefficients()
    row = coefs.filter(pl.col("term") == "consecutive_matches").row(0, named=True)
    return float(row["coef"])


def test_naive_biased_vs_eligible_target(
    fitted: tuple[DiscreteHazardModel, DiscreteHazardModel, WeightedHazardModel],
) -> None:
    naive, target, _ = fitted
    beta_target = _load_coef(target)
    beta_naive = _load_coef(naive)
    # Conditionner sur played (collider) déplace nettement le coefficient de X.
    assert abs(beta_naive - beta_target) > 0.01


def test_ipw_halves_error_vs_target(
    fitted: tuple[DiscreteHazardModel, DiscreteHazardModel, WeightedHazardModel],
) -> None:
    naive, target, weighted = fitted
    assert weighted.hazard_ is not None
    beta_target = _load_coef(target)
    err_naive = abs(_load_coef(naive) - beta_target)
    err_ipw = abs(_load_coef(weighted.hazard_) - beta_target)
    assert err_ipw <= 0.5 * err_naive


def test_ipw_enabled_and_calibrated(
    fitted: tuple[DiscreteHazardModel, DiscreteHazardModel, WeightedHazardModel],
) -> None:
    _, _, weighted = fitted
    diag = weighted.diagnostics_
    assert diag is not None
    assert diag.slope_ok, f"pente hors gate : {diag.slope}"
    assert diag.ipw_enabled is True
    assert weighted.hazard_.weighted_ is True  # type: ignore[union-attr]
    assert weighted.warning_ is None


def test_gate_disables_ipw_when_miscalibrated(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(SelectionModel, "calibration_slope_cv", lambda self, eligible: 9.9)
    df = selection_frame(seed=1)
    played = df.filter(pl.col("played"))
    model = WeightedHazardModel(curve_replications=0, spec=SPEC).fit(played, eligible=df)
    diag = model.diagnostics_
    assert diag is not None and diag.ipw_enabled is False and diag.slope_ok is False
    assert model.warning_ is not None
    assert model.hazard_ is not None and model.hazard_.weighted_ is False
