"""F20 design matrix: train-only transformations, no forbidden columns."""

import numpy as np
import polars as pl
import pytest

from rugby_risk.modeling.design import DesignSpec, build_design, validate_spec
from tests.hazard_factory import hazard_frame

LINEAR = DesignSpec(
    categorical=("position_group",),
    splines=(),
    linear=("min_28d",),
    interactions=(),
)


def test_standardisation_learned_on_train_is_reapplied() -> None:
    df = hazard_frame(players=60, seasons=2, seed=3)
    train = df.filter(pl.col("season_id") == "2020-2021")
    # Test fold shifted on purpose: its own mean/std must not be used.
    test = df.filter(pl.col("season_id") == "2021-2022").with_columns(pl.col("min_28d") + 500)
    fitted = build_design(train, LINEAR)
    applied = build_design(test, LINEAR, fitted.transform)
    t = fitted.transform
    col = applied.columns.index("min_28d")
    lo, hi = t.bounds["min_28d"]
    expected = (np.clip(test["min_28d"].to_numpy(), lo, hi) - t.means["min_28d"]) / t.stds[
        "min_28d"
    ]
    np.testing.assert_allclose(applied.X[:, col], expected)
    # Winsorisation aux bornes du train : le décalage de +500 est plafonné.
    assert applied.X[:, col].max() == pytest.approx((hi - t.means["min_28d"]) / t.stds["min_28d"])


def test_splines_knots_reused_on_subset() -> None:
    train = hazard_frame(players=60, seasons=1, seed=4)
    fitted = build_design(train, DesignSpec())
    subset = build_design(train[:50], DesignSpec(), fitted.transform)
    np.testing.assert_allclose(subset.X, fitted.X[:50])
    assert subset.columns == fitted.columns


@pytest.mark.parametrize(
    "spec",
    [
        DesignSpec(linear=("minutes_played",)),
        DesignSpec(linear=("y_injury_any_7d",)),
        DesignSpec(categorical=("player_key",)),
        DesignSpec(linear=("is_starter",)),
    ],
)
def test_forbidden_columns_rejected(spec: DesignSpec) -> None:
    with pytest.raises(ValueError, match="interdites"):
        validate_spec(spec)


def test_degenerate_terms_dropped_and_listed() -> None:
    df = hazard_frame(players=40, seasons=1, seed=5).with_columns(
        pl.lit(None, dtype=pl.Float64).alias("age"),
        pl.lit("2018_2026").alias("season_period"),
        pl.lit(False).alias("short_turnaround"),
        # 5 lignes seulement en phase finale : support < min_binary_support.
        (pl.int_range(pl.len()) < 5).alias("is_playoff"),
    )
    t = build_design(df, DesignSpec()).transform
    assert {"age", "season_period", "short_turnaround", "is_playoff"} <= set(t.dropped)
    assert "age" not in t.formula and "is_playoff" not in t.formula


def test_unseen_category_falls_back_to_reference() -> None:
    train = hazard_frame(players=40, seasons=1, seed=6)
    fitted = build_design(train, DesignSpec())
    test = train[:3].with_columns(pl.lit("synthetic_turf").alias("surface"))
    out = build_design(test, DesignSpec(), fitted.transform)
    assert out.X.shape == (3, len(fitted.columns))


def test_offset_requires_positive_minutes() -> None:
    df = hazard_frame(players=10, seasons=1, seed=7)
    with pytest.raises(ValueError, match="exposition positive"):
        build_design(df.with_columns(pl.lit(0).alias("minutes_played")), DesignSpec())
    np.testing.assert_allclose(
        build_design(df, DesignSpec()).offset, np.log(df["minutes_played"].to_numpy() / 80)
    )


def test_interactions_have_reference_level_omitted() -> None:
    t = build_design(hazard_frame(players=60, seasons=1, seed=8), DesignSpec()).transform
    groups = t.levels["position_group"]
    names = [c for c in t.formula.split(" + ") if c.startswith("consecutive_matches__x__")]
    # Une pente par groupe hors référence : sinon colinéarité avec cr(consecutive_matches).
    assert len(names) == len(groups) - 1
    assert all(groups[0] not in n for n in names)


def test_binary_features_not_standardised() -> None:
    df = hazard_frame(players=40, seasons=1, seed=12)
    d = build_design(df, DesignSpec())
    col = d.columns.index("intl_window")
    assert set(np.unique(d.X[:, col])) == {0.0, 1.0}
    assert d.transform.stds["intl_window"] == 1.0
