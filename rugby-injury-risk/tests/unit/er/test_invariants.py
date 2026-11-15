from datetime import date

import polars as pl
import pytest

from rugby_risk.entity_resolution.invariants import (
    check_no_double_sheet_same_day,
    check_stable_ids,
    check_unique_source_id,
)

pytestmark = pytest.mark.unit


def test_unique_source_id_ok_and_violation():
    ok = pl.DataFrame(
        {"source": ["lnr", "allrugby"], "source_player_id": ["1", "9"], "player_id": [1, 1]}
    )
    assert check_unique_source_id(ok).is_empty()
    bad = pl.DataFrame(
        {"source": ["lnr", "lnr"], "source_player_id": ["1", "1"], "player_id": [1, 2]}
    )
    assert check_unique_source_id(bad).height == 2


def test_double_sheet_same_day():
    apps = pl.DataFrame(
        {
            "key": ["lnr:1", "allrugby:9", "lnr:2"],
            "match_key": ["m1", "m1", "m2"],
            "match_date": [date(2024, 2, 2), date(2024, 2, 2), date(2024, 2, 2)],
        }
    )
    xref = pl.DataFrame({"key": ["lnr:1", "allrugby:9", "lnr:2"], "player_id": [1, 1, 2]})
    assert check_no_double_sheet_same_day(xref, apps, None).is_empty()
    bad = xref.with_columns(pl.Series("player_id", [1, 1, 1]))
    violations = check_no_double_sheet_same_day(bad, apps, None)
    assert violations["player_id"].to_list() == [1]


def test_stable_ids():
    previous = pl.DataFrame({"key": ["a:1", "a:2"], "player_id": [1, 2]})
    same = pl.DataFrame({"key": ["a:1", "a:2", "a:3"], "player_id": [1, 2, 3]})
    assert check_stable_ids(same, previous).is_empty()
    moved = pl.DataFrame({"key": ["a:1", "a:2"], "player_id": [2, 2]})
    assert check_stable_ids(moved, previous).height == 1
