from datetime import UTC, datetime

import pytest

from rugby_risk.calendar import build_calendar
from rugby_risk.warehouse import staging_frame

pytestmark = pytest.mark.unit


def _row(source, home, hour, **extra):
    return {
        "source": source,
        "source_match_id": source,
        "competition_code": "TOP14",
        "season_id": "2023-2024",
        "round": None,
        "kickoff_ts": datetime(2023, 12, 2, hour, 5, tzinfo=UTC),
        "kickoff_time_imputed": False,
        "venue_name": None,
        "home_team_name": home,
        "away_team_name": "RC Toulon",
        "home_score": None,
        "away_score": None,
    } | extra


def test_priority_conflict_and_unresolved():
    matches = staging_frame(
        "match",
        [
            _row("espn", "Toulouse", 20, round="R10"),
            _row("lnr", "Stade Toulousain", 17, venue_name="Stade Ernest-Wallon"),
            _row("allrugby", "Stade Toulousain", 14, kickoff_time_imputed=True),
            _row("allrugby", "Club Inconnu", 14),
        ],
    )
    calendar, conflicts, unresolved = build_calendar(matches)
    assert calendar.height == 2
    top = calendar.filter(calendar["home_team_name"] == "Stade Toulousain").row(0, named=True)
    assert (top["source"], top["kickoff_ts"].hour, top["round"], top["venue_id"]) == (
        "lnr",
        17,
        "R10",
        1,
    )
    assert conflicts["sources"].to_list() == ["espn,lnr"]  # 3 h d'écart, l'imputée ignorée
    assert unresolved == {"Club Inconnu"}


def test_empty():
    calendar, conflicts, unresolved = build_calendar(staging_frame("match", []))
    assert calendar.is_empty() and conflicts.is_empty() and unresolved == set()
