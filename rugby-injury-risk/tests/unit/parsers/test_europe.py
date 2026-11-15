from pathlib import Path

import pytest

from rugby_risk.parsers.espn import parse_europe, parse_scoreboard
from rugby_risk.reference import team_canonical

pytestmark = pytest.mark.unit
FIXTURES = Path("tests/fixtures/espn")


def _europe(name):
    result = parse_europe((FIXTURES / name).read_text())
    assert result is not None
    return result


def test_champions_cup_pool():
    match, apps = _europe("champions_cup_pool.json")
    assert match["competition_code"] == "CHAMPIONS_CUP"
    assert match["season_id"] == "2023-2024"
    assert match["round"] == "R2"
    assert team_canonical(str(match["home_team_name"]), "espn") == "Stade Toulousain"
    assert len(apps) == 46


def test_challenge_cup_quarter_final():
    match, _ = _europe("challenge_cup_qf.json")
    assert (match["competition_code"], match["round"]) == ("CHALLENGE_CUP", "Quarter-final")
    assert team_canonical(str(match["home_team_name"]), "espn") == "ASM Clermont Auvergne"


def test_out_of_scope_skipped():
    assert (
        parse_europe((FIXTURES / "champions_cup_no_french.json").read_text()) is None
    )  # sans club
    assert parse_europe((FIXTURES / "rwc_summary.json").read_text()) is None  # pas une coupe


def test_scoreboard_calendar_page():
    rows = parse_scoreboard((FIXTURES / "scoreboard_champions_cup.json").read_text())
    assert [r["source_match_id"] for r in rows] == ["910001", "910004"]
    assert {r["competition_code"] for r in rows} == {"CHAMPIONS_CUP"}
    assert rows[1]["round"] == "R5" and rows[1]["home_score"] is None


def test_scoreboard_out_of_scope_league():
    payload = (FIXTURES / "scoreboard_champions_cup.json").read_text()
    assert parse_scoreboard(payload.replace("Investec Champions Cup", "Women's Six Nations")) == []
