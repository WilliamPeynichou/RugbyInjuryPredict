from pathlib import Path

import pytest

from rugby_risk import reference
from rugby_risk.parsers.allrugby.match import MatchParseError
from rugby_risk.parsers.allrugby.match import parse_match as parse_allrugby
from rugby_risk.parsers.espn import parse_scoreboard, parse_summary
from rugby_risk.parsers.lnr import parse_lineup
from rugby_risk.parsers.worldrugby import parse_match as parse_worldrugby

pytestmark = pytest.mark.unit
FIX = Path("tests/fixtures")


def test_aliases_point_to_known_entities():
    teams = reference.team_aliases()
    assert not teams.select("raw_name", "source").is_duplicated().any()
    # Une équipe canonique = une identité (pays, sélection) ; chacune a son propre alias `*`.
    canonical = set(teams["team_canonical"])
    assert canonical <= set(teams.filter(teams["source"] == "*")["raw_name"])
    venues = reference.venue_aliases()
    assert not venues["raw_name"].is_duplicated().any()
    assert set(venues["venue_id"]) <= set(reference.venues()["venue_id"])


def test_lookups():
    assert reference.team_canonical("Toulouse", "espn") == "Stade Toulousain"
    assert reference.team_canonical("Toulouse", "lnr") is None  # alias propre à ESPN
    assert reference.team_canonical("France", "worldrugby") == "France"
    assert reference.is_french_club("Stade Toulousain")
    assert not reference.is_french_club("France") and not reference.is_french_club(None)
    assert reference.venue_id("Stade Ernest Wallon") == 1
    assert reference.venue_id(None) is None


def _fixture_matches():
    for path in (FIX / "allrugby").glob("match_*.html"):
        try:
            yield parse_allrugby(path.read_text(), "2023-2024")[0]
        except MatchParseError:
            continue  # quarantaine légitime (ex. page Pro D2 hors périmètre)
    for path in (FIX / "lnr").glob("lineup_*.html"):
        yield parse_lineup(path.read_text(), "2024-2025")[0]
    for name in (
        "champions_cup_pool",
        "challenge_cup_qf",
        "champions_cup_no_french",
        "rwc_summary",
    ):
        yield parse_summary((FIX / "espn" / f"{name}.json").read_text())[0]
    yield from parse_scoreboard((FIX / "espn" / "scoreboard_champions_cup.json").read_text())
    for name in ("six_nations", "november_test", "rwc"):
        yield parse_worldrugby((FIX / "worldrugby" / f"{name}_summary.json").read_text(), None)[0]


def test_all_fixture_teams_resolved():
    unresolved = {
        (m["source"], m[side])
        for m in _fixture_matches()
        for side in ("home_team_name", "away_team_name")
        if reference.team_canonical(str(m[side]), str(m["source"])) is None
    }
    assert unresolved == set()
