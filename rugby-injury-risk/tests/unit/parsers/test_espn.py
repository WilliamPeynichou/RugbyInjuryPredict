from pathlib import Path

import pytest

from rugby_risk.parsers.espn import parse_summary
from rugby_risk.parsers.intl import IntlParseError

pytestmark = pytest.mark.unit
FIXTURES = Path("tests/fixtures/espn")


def test_lineups_and_replacements():
    match, apps = parse_summary((FIXTURES / "rwc_summary.json").read_text())
    assert match["source"] == "espn" and match["source_match_id"] == "900001"
    assert match["competition_code"] == "RWC"
    assert match["season_id"] == "2023-2024"
    assert (match["home_score"], match["away_score"]) == (27, 13)
    assert match["venue_name"] == "Stade Fictif"
    assert len(apps) == 45
    starters = [a for a in apps if a["is_starter"]]
    assert len(starters) == 30  # maillot 1-15, le drapeau `starter` ESPN est ignoré
    bench = [a for a in apps if not a["is_starter"]]
    assert {a["shirt_number"] for a in bench} == set(range(16, 24))
    assert {a["minutes_played"] for a in apps} == {None}
    assert next(a for a in apps if a["shirt_number"] == 2)["position_raw"] == "HOOKER"


def test_missing_rosters_quarantined():
    with pytest.raises(IntlParseError, match="Compositions absentes"):
        parse_summary((FIXTURES / "incomplete_summary.json").read_text())


def test_missing_header_quarantined():
    with pytest.raises(IntlParseError, match=r"header\.id"):
        parse_summary("{}")
