from datetime import date

import polars as pl
import pytest

from rugby_risk.entity_resolution.resolve import resolve_entities

pytestmark = pytest.mark.unit

RECORDS = pl.DataFrame(
    {
        "key": ["lnr:1", "allrugby:9", "espn:5"],
        "source": ["lnr", "allrugby", "espn"],
        "source_player_id": ["1", "9", "5"],
        "name_norm": ["antoine dupont", "antoine dupont", "antoine dupont"],
        "name_block": ["a", "a", "a"],
        "birth_date": [None, None, None],
        "birth_year": [None, None, None],
        "nationality": [None, None, None],
        "teams": [None, None, None],
    }
)


def _resolve(anchor=None, scored=None, previous=None, overrides=None):
    anchor = (
        anchor
        if anchor is not None
        else pl.DataFrame(schema={"key_l": pl.String, "key_r": pl.String, "anchor": pl.Boolean})
    )
    scored = (
        scored
        if scored is not None
        else pl.DataFrame(
            schema={"key_l": pl.String, "key_r": pl.String, "match_probability": pl.Float64}
        )
    )
    overrides = (
        overrides
        if overrides is not None
        else pl.DataFrame(schema={"key": pl.String, "player_id": pl.String})
    )
    apps = pl.DataFrame(
        {
            "key": ["lnr:1", "allrugby:9", "espn:5"],
            "match_key": ["m1", "m1", "m2"],
            "match_date": [date(2024, 2, 2), date(2024, 2, 2), date(2024, 2, 2)],
        }
    )
    return resolve_entities(RECORDS, anchor, scored, apps, previous, overrides)


def test_anchor_links_and_method():
    anchor = pl.DataFrame({"key_l": ["lnr:1"], "key_r": ["allrugby:9"], "anchor": [True]})
    xref, _queue = _resolve(anchor=anchor)
    ids = dict(zip(xref["key"], xref["player_id"], strict=True))
    assert ids["lnr:1"] == ids["allrugby:9"]
    assert set(xref.filter(xref["key"] != "espn:5")["method"]) == {"anchor_lnr"}
    assert xref.filter(xref["key"] == "espn:5")["method"].to_list() == ["splink"]


def test_review_range_goes_to_queue():
    scored = pl.DataFrame({"key_l": ["lnr:1"], "key_r": ["espn:5"], "match_probability": [0.8]})
    xref, queue = _resolve(scored=scored)
    assert queue.height == 1
    assert set(xref["player_id"]) == {1, 2, 3}  # aucune fusion sous le seuil auto


def test_blocked_merge_two_matches_same_day_goes_to_queue():
    anchor = pl.DataFrame({"key_l": ["lnr:1"], "key_r": ["allrugby:9"], "anchor": [True]})
    scored = pl.DataFrame(
        {"key_l": ["allrugby:9"], "key_r": ["espn:5"], "match_probability": [0.99]}
    )
    _, queue = _resolve(anchor=anchor, scored=scored)
    assert queue["match_probability"].to_list() == [None]  # fusion bloquée (2 matchs, même jour)


def test_override_priority_and_reject():
    overrides = pl.DataFrame({"key": ["espn:5", "allrugby:9"], "player_id": ["42", "REJECT"]})
    xref, _ = _resolve(overrides=overrides)
    row = xref.filter(xref["key"] == "espn:5").row(0, named=True)
    assert (row["player_id"], row["method"]) == (42, "manual_override")
    assert "allrugby:9" not in xref["key"].to_list()


def test_stable_ids_reuse_previous():
    anchor = pl.DataFrame({"key_l": ["lnr:1"], "key_r": ["allrugby:9"], "anchor": [True]})
    previous = pl.DataFrame({"key": ["lnr:1"], "player_id": [7]})
    xref, _ = _resolve(anchor=anchor, previous=previous)
    ids = dict(zip(xref["key"], xref["player_id"], strict=True))
    assert ids["lnr:1"] == ids["allrugby:9"] == 7
