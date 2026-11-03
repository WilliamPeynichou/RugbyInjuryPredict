import pytest

from rugby_risk.parsers.lnr import (
    LineupParseError,
    normalize_position,
    parse_lineup,
)

pytestmark = pytest.mark.unit
FIXTURES = "tests/fixtures/lnr"


def _load(name):
    return open(f"{FIXTURES}/{name}", encoding="utf-8").read()


def test_regular_lineup():
    match, apps = parse_lineup(_load("lineup_regular.html"), "2024-2025")
    assert match["source"] == "lnr"
    assert match["source_match_id"] == "8427"
    assert match["round"] == "J10"
    assert match["season_id"] == "2024-2025"
    assert match["kickoff_time_imputed"] is False
    assert match["kickoff_ts"].hour == 20 and match["kickoff_ts"].minute == 5  # 21:05 Paris (UTC+1)
    assert match["venue_name"] == "Stade Ernest-Wallon"
    assert match["home_score"] == 27 and match["away_score"] == 19
    assert len(apps) == 46
    starters = [a for a in apps if a["is_starter"]]
    assert len(starters) == 30
    baille = next(a for a in apps if a["player_name"] == "Cyril BAILLE")
    assert baille["source_player_id"] == "9182"
    assert baille["shirt_number"] == 1 and baille["is_starter"] is True
    assert baille["position_raw"] == "PROP"
    assert baille["minutes_played"] is None  # la LNR ne donne pas les minutes
    marchand = next(a for a in apps if a["player_name"] == "Julien MARCHAND")
    assert marchand["is_starter"] is False and marchand["shirt_number"] == 17
    willis = next(a for a in apps if a["player_name"] == "Jack WILLIS")
    assert willis["position_raw"] == "BACK_ROW"


def test_playoff_lineup():
    match, apps = parse_lineup(_load("lineup_playoff.html"), "2024-2025")
    assert match["round"] == "Demi"
    assert match["source_match_id"] == "8431"
    assert len(apps) == 46


def test_late_change_lineup():
    match, apps = parse_lineup(_load("lineup_late_change.html"), "2024-2025")
    assert match["round"] == "J11"
    assert match["kickoff_time_imputed"] is True  # date seule -> 15:00 Paris imputée
    assert match["kickoff_ts"].hour == 14  # 29/12/2024 : Paris UTC+1
    assert len(apps) == 46


def test_invalid_page_quarantined():
    with pytest.raises(LineupParseError):
        parse_lineup("<html><body>rien</body></html>", "2024-2025")


def test_position_normalization():
    assert normalize_position("Pilier gauche") == "PROP"
    assert normalize_position("Demi de mêlée") == "SCRUM_HALF"
    assert normalize_position("Inconnu") == "unknown"
