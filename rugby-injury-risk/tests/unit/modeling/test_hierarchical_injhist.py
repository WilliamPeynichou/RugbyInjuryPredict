"""M2 injhist : variante « historique de blessure ». Aucun .fit() MCMC ici (design et registre).

La sentinelle 999 (« jamais blessé ») n'est jamais lue comme une durée : elle est portée par
l'indicateur `ever_injured`. Le plafond log1p est appris sur le train, réutilisé sur la validation.
"""

import json
from pathlib import Path

import numpy as np
import polars as pl
import pytest

from rugby_risk.modeling.design import (
    INJURY_LOG_CAP_DAYS,
    INJURY_NEVER_SENTINEL,
    build_design,
)
from rugby_risk.modeling.hierarchical import (
    FIXED_SPEC,
    INJHIST_SPEC,
    HierarchicalHazardModel,
)
from rugby_risk.modeling.null import registry
from tests.hazard_factory import hazard_frame

pytestmark = pytest.mark.unit

# Chaîne de formule M2 de référence, lue dans data/models/m2_hierarchical-20261108T234650Z/meta.json
# AVANT toute modification de hierarchical.py (règle : la référence ne doit jamais bouger).
M2_REFERENCE_FORMULA = (
    "cr(apps_20min_365d, df=3, constraints='center') + "
    "cr(days_since_last_match_capped, df=3, constraints='center') + "
    "consecutive_matches + min_28d + intl_window + recent_return_8w + n_prior_injuries_365d"
)


def _frame_with_injury(seed: int = 4) -> pl.DataFrame:
    """Frame synthétique + days_since_last_injury (ajoutée ici, la factory n'est pas modifiée)."""
    df = hazard_frame(players=80, seasons=2, matches=10, seed=seed)
    rng = np.random.default_rng(seed)
    n = len(df)
    values = rng.choice([999, 7, 42, 400, 1001], size=n).astype(np.int32)
    return df.with_columns(pl.Series("days_since_last_injury", values))


def test_registry_exposes_injhist_variant() -> None:
    factories = registry()
    assert "m2_hierarchical_injhist" in factories
    model = factories["m2_hierarchical_injhist"]()
    assert isinstance(model, HierarchicalHazardModel)
    assert model.name == "m2_hierarchical_injhist"
    assert model.registry_name == "rugby-risk-m2-injhist"
    assert model.spec is INJHIST_SPEC


def test_injhist_registry_name_distinct_from_production() -> None:
    reference = HierarchicalHazardModel()
    variant = registry()["m2_hierarchical_injhist"]()
    assert reference.registry_name == "rugby-risk-m2"
    assert variant.registry_name != reference.registry_name
    assert variant.name != reference.name


def test_reference_m2_spec_unchanged() -> None:
    # FIXED_SPEC intact : pas d'indicateur d'historique, défaut du M2 de production.
    assert HierarchicalHazardModel().spec is FIXED_SPEC
    assert "ever_injured" not in FIXED_SPEC.linear
    assert "log1p_days_since_injury" not in FIXED_SPEC.linear


def test_reference_formula_string_unchanged() -> None:
    # Le M2 de référence reconstruit la formule STOCKÉE de l'artefact réel (frame
    # design_frame.parquet) : pas de dérive. La chaîne vient de meta.json, jamais recopiée.
    artifact = Path("data/models/m2_hierarchical-20261108T234650Z")
    if not (artifact / "meta.json").exists():
        pytest.skip("artefact M2 de référence absent de ce dépôt")
    meta = json.loads((artifact / "meta.json").read_text(encoding="utf-8"))
    frame = pl.read_parquet(artifact / "design_frame.parquet")
    formula = build_design(frame, FIXED_SPEC).transform.formula
    assert formula == meta["transform"]["formula"]
    assert "ever_injured" not in formula
    assert "log1p_days_since_injury" not in formula
    assert formula == M2_REFERENCE_FORMULA


def test_injhist_adds_exactly_two_columns() -> None:
    df = _frame_with_injury()
    train = df.filter(pl.col("season_id") == "2020-2021")
    base = build_design(train, FIXED_SPEC)
    variant = build_design(train, INJHIST_SPEC)
    added = set(variant.columns) - set(base.columns)
    assert added == {"ever_injured", "log1p_days_since_injury"}
    assert variant.X.shape[1] == base.X.shape[1] + 2


def test_design_has_no_nan_or_inf() -> None:
    df = _frame_with_injury()
    train = df.filter(pl.col("season_id") == "2020-2021")
    valid = df.filter(pl.col("season_id") == "2021-2022")
    fitted = build_design(train, INJHIST_SPEC)
    applied = build_design(valid, INJHIST_SPEC, fitted.transform)
    assert np.isfinite(fitted.X).all()
    assert np.isfinite(applied.X).all()


def test_sentinel_never_read_as_days() -> None:
    df = _frame_with_injury()
    train = df.filter(pl.col("season_id") == "2020-2021")
    fitted = build_design(train, INJHIST_SPEC)
    ever = fitted.X[:, fitted.columns.index("ever_injured")]
    log_days = fitted.X[:, fitted.columns.index("log1p_days_since_injury")]
    # Sentinelle 999 exacte : indicateur 0 ; les vraies durées : indicateur 1.
    raw = train["days_since_last_injury"].to_numpy()
    sentinel = raw == INJURY_NEVER_SENTINEL
    assert sentinel.any() and (~sentinel).any()
    # Le design standardise les colonnes : on contrôle via les statistiques apprises.
    t = fitted.transform
    assert t.means.get("ever_injured", 0.0) == 0.0  # binaire : non centrée
    assert t.stds.get("ever_injured", 1.0) == 1.0
    assert set(np.unique(ever)).issubset({0.0, 1.0})
    # Le log1p du sentinelle n'est pas le log1p de 999 : il vaut 0 (après standardisation,
    # la valeur brute 0 devient une constante, pas log(1000)).
    assert not np.isclose(log_days[sentinel].max(), np.log1p(INJURY_NEVER_SENTINEL))


def test_ever_injured_is_one_for_real_injuries() -> None:
    frame = pl.DataFrame(
        {"days_since_last_injury": [999, 7, 1001, 400], "minutes_played": [80, 80, 80, 80]}
    )
    from rugby_risk.modeling.design import _ever_injured  # noqa: PLC0415

    flags = frame.select(_ever_injured(pl.col("days_since_last_injury")).alias("e"))["e"]
    assert flags.to_list() == [0.0, 1.0, 1.0, 1.0]


def test_log_capped_at_train_ceiling_and_reused_on_validation() -> None:
    df = _frame_with_injury()
    train = df.filter(pl.col("season_id") == "2020-2021")
    # Validation : valeurs au-delà du plafond, jamais vues au train.
    valid = df.filter(pl.col("season_id") == "2021-2022").with_columns(
        pl.lit(5000, dtype=pl.Int32).alias("days_since_last_injury")
    )
    fitted = build_design(train, INJHIST_SPEC)
    applied = build_design(valid, INJHIST_SPEC, fitted.transform)
    col = applied.columns.index("log1p_days_since_injury")
    # Au-delà du plafond, la valeur est identique au plafond : pas de recalcul sur la validation.
    ceiling = np.log1p(INJURY_LOG_CAP_DAYS)
    expected_raw = np.full(len(valid), ceiling)
    t = fitted.transform
    # Le design standardise les valeurs continues : même transformation que le train.
    if "log1p_days_since_injury" in t.means:
        expected = (expected_raw - t.means["log1p_days_since_injury"]) / t.stds[
            "log1p_days_since_injury"
        ]
    else:
        expected = expected_raw
    np.testing.assert_allclose(applied.X[:, col], expected, rtol=1e-9)
