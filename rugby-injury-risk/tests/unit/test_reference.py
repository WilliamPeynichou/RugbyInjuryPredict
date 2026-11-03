from datetime import date
from pathlib import Path

import polars as pl
import pytest

from rugby_risk import reference
from rugby_risk.config.seasons import load_seasons

pytestmark = pytest.mark.unit


@pytest.mark.parametrize(
    "name",
    [
        "positions",
        "competitions",
        "venues",
        "venue_surface",
        "test_windows",
        "rules_protection",
        "protected_players",
        "opt_out",
        "er_overrides",
    ],
)
def test_csv_schema(name):
    assert isinstance(getattr(reference, name)(), pl.DataFrame)


def test_positions():
    frame = reference.positions()
    assert (frame.height, frame["position_group"].n_unique(), frame["unit"].n_unique()) == (9, 6, 2)
    assert reference.position_from_shirt(2) == "HOOKER"
    assert reference.position_from_shirt(18) is None
    assert reference.position_from_shirt(0) is None
    assert reference.position_group("HOOKER") == "front_row"
    with pytest.raises(ValueError, match="Unknown position"):
        reference.position_group("invalid")


def test_no_position_literals_in_source():
    for path in Path("src").rglob("*.py"):
        content = path.read_text()
        for code in reference.positions()["position_code"]:
            assert f'"{code}"' not in content
            assert f"'{code}'" not in content


def test_windows_cover_seasons():
    windows = reference.test_windows()
    for season in load_seasons():
        assert not windows.filter(
            (pl.col("start_date") <= season.end_date) & (pl.col("end_date") >= season.start_date)
        ).is_empty()
    assert reference.in_test_window(date(2024, 2, 10))
    assert not reference.in_test_window(date(2020, 7, 1))
    assert reference.in_test_window(date(2020, 10, 24))
    assert reference.in_test_window(date(2020, 12, 6))
    assert reference.in_test_window(date(2026, 7, 4))
    assert reference.in_test_window(date(2026, 11, 29))
    assert not reference.in_test_window(date(2026, 8, 1))


def test_regime():
    assert reference.protection_regime(date(2026, 7, 1)) == "protected_33"
    assert reference.protection_regime(date(2026, 6, 30)) == "expanded_squads"
    assert reference.protection_regime(date(2014, 6, 1)) == "elite_30"
    assert reference.protection_regime(date(2015, 6, 1)) == "unknown"
    assert reference.protection_regime(date(2013, 1, 1)) == "unknown"


def test_invalid_intervals():
    frame = pl.DataFrame(
        {
            "start_date": [date(2024, 2, 1), date(2024, 2, 10)],
            "end_date": [date(2024, 2, 12), date(2024, 2, 20)],
            "type": ["summer", "summer"],
        }
    )
    assert not reference._intervals(frame, "type")
    assert reference._intervals(frame.with_columns(pl.Series("type", ["summer", "autumn"])), "type")
    assert not reference._intervals(frame.with_columns(pl.lit(date(2020, 1, 1)).alias("end_date")))


def test_cache_not_mutable():
    frame = reference.positions()
    frame.drop_in_place("unit")
    assert "unit" in reference.positions().columns
