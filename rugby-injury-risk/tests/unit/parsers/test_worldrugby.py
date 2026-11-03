import json
from pathlib import Path

import pytest

from rugby_risk.parsers.intl import IntlParseError, competition_code
from rugby_risk.parsers.worldrugby import parse_match
from rugby_risk.reference import competitions

pytestmark = pytest.mark.unit
FIXTURES = Path("tests/fixtures/worldrugby")


def _parse(name, with_timeline=True):
    timeline = (FIXTURES / f"{name}_timeline.json").read_text() if with_timeline else None
    return parse_match((FIXTURES / f"{name}_summary.json").read_text(), timeline)


def _by_id(apps):
    return {a["source_player_id"]: a for a in apps}


def test_six_nations_minutes_rebuilt():
    match, apps = _parse("six_nations")
    assert match["competition_code"] == "SIX_NATIONS"
    assert match["season_id"] == "2023-2024"
    assert match["home_team_name"] == "France" and match["away_score"] == 38
    players = _by_id(apps)
    assert len(apps) == 46
    assert players["fra-1"]["minutes_played"] == 50  # Sub Off 50'
    assert players["fra-17"]["minutes_played"] == 30  # Sub On 50'
    assert players["fra-4"]["minutes_played"] == 20  # IR = bascule (sortie)
    assert players["fra-19"]["minutes_played"] == 60  # IR = bascule (entrée)
    assert players["fra-11"]["minutes_played"] == 80  # essai ignoré
    assert players["fra-20"]["minutes_played"] == 0  # remplaçant non entré
    assert players["fra-6"]["yellow_cards"] == 1
    assert players["fra-17"]["is_starter"] is False
    assert players["fra-1"]["position_raw"] == "PROP"
    totals = {
        t: sum(a["minutes_played"] for a in apps if a["team_name"] == t)
        for t in ("France", "Ireland")
    }
    assert totals == {"France": 1200, "Ireland": 1200}


def test_november_generic_label_mapped_by_month_and_red_card():
    match, apps = _parse("november_test")
    assert match["competition_code"] == "AUTUMN_TESTS"
    assert match["season_id"] == "2024-2025"
    sent_off = _by_id(apps)["new-5"]
    assert sent_off["minutes_played"] == 60 and sent_off["red_cards"] == 1


def test_rwc_mapped():
    match, _ = _parse("rwc")
    assert match["competition_code"] == "RWC"


def test_no_timeline_gives_null_minutes():
    _, apps = _parse("six_nations", with_timeline=False)
    assert {a["minutes_played"] for a in apps} == {None}


def test_incomplete_json_quarantined():
    with pytest.raises(IntlParseError, match="15 titulaires"):
        _parse("incomplete", with_timeline=False)


def test_missing_match_id_quarantined():
    payload = json.loads((FIXTURES / "rwc_summary.json").read_text())
    del payload["match"]["matchId"]
    with pytest.raises(IntlParseError, match="matchId"):
        parse_match(json.dumps(payload))


def test_out_of_scope_competitions():
    from datetime import date  # noqa: PLC0415

    for label in ("Women's Six Nations 2024", "HSBC Sevens", "U20 Six Nations"):
        with pytest.raises(IntlParseError, match="Hors périmètre"):
            competition_code(label, date(2024, 2, 2))
    assert competition_code("Summer Nations Series", date(2024, 7, 1)) == "SUMMER_TESTS"
    assert competition_code("Test", date(2024, 7, 1)) == "SUMMER_TESTS"
    assert competition_code("Test", date(2024, 3, 1)) == "OTHER_TEST"


def test_all_mapped_codes_exist():
    import polars as pl  # noqa: PLC0415

    known = set(competitions()["competition_code"].to_list())
    aliases = pl.read_csv("data/reference/competition_aliases.csv")
    assert (
        set(aliases["competition_code"].to_list()) | {"AUTUMN_TESTS", "SUMMER_TESTS", "OTHER_TEST"}
        <= known
    )
