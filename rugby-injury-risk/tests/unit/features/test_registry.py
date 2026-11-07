import pytest

from rugby_risk.features import registry

pytestmark = pytest.mark.unit


def test_each_column_in_exactly_one_list():
    lists = (
        registry.ID_COLUMNS,
        registry.TARGET_AND_EXPOSURE_COLUMNS,
        registry.FEATURES_NUMERIC,
        registry.FEATURES_CATEGORICAL,
    )
    flat = [c for cols in lists for c in cols]
    assert len(flat) == len(set(flat))
    assert set(flat) == set(registry.ALL_COLUMNS)


def test_no_forbidden_or_leaky_feature():
    assert not registry.FORBIDDEN_COLUMNS & set(registry.ALL_COLUMNS)
    assert set(registry.FEATURES_NUMERIC) >= registry.FLOAT_FEATURES
    # docs/05 : ni ACWR ni données du match t dans les features.
    assert not {c for c in registry.FEATURES if "acwr" in c or c.startswith("y_")}
    assert "minutes_played" not in registry.FEATURES
