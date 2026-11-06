import pytest

from rugby_risk.parsers.allrugby.match import MatchParseError, parse_match

pytestmark = pytest.mark.unit
FIXTURES = "tests/fixtures/allrugby"


def _load(name):
    return open(f"{FIXTURES}/{name}", encoding="utf-8").read()


def _team_minutes(apps, team):
    return sum(a["minutes_played"] for a in apps if a["team_name"] == team)


def test_standard_match():
    match, apps = parse_match(_load("match_standard.html"), "2023-2024")
    assert match["source_match_id"] == "19357" and match["round"] == "J22"
    assert match["kickoff_time_imputed"] is False
    assert match["kickoff_ts"].isoformat() == "2024-04-27T15:00:00+00:00"  # 17h00 Paris
    assert match["venue_name"] == "Stade Jean Dauger"
    assert (match["home_team_name"], match["away_team_name"]) == ("Bayonne", "Bordeaux")
    assert (match["home_score"], match["away_score"]) == (15, 34)
    assert len(apps) == 46 and sum(a["is_starter"] for a in apps) == 30
    assert _team_minutes(apps, "Bayonne") == _team_minutes(apps, "Bordeaux") == 15 * 80
    huguet = next(a for a in apps if a["player_name"] == "Pierre HUGUET")
    assert huguet["minutes_played"] == 54 + (80 - 74)  # sorti 54', revenu 74'
    assert huguet["position_raw"] == "BACK_ROW" and huguet["source_player_id"] == "3660"
    assert (
        next(a for a in apps if a["shirt_number"] == 16)["position_raw"] == "unknown"
    )  # banc : poste non déduit


def test_reentry_and_missing_venue():
    match, apps = parse_match(_load("match_reentry_no_venue.html"), "2023-2024")
    assert match["venue_name"] is None and match["round"] == "J1"
    heguy = next(a for a in apps if a["player_name"] == "Baptiste HÉGUY")
    assert heguy["minutes_played"] == 48  # 46' + 2' : valeur de la page joueur allrugby


def test_final_with_yellow_card():
    match, apps = parse_match(_load("match_final_yellow.html"), "2023-2024")
    assert match["round"] == "Finale"
    carded = [a for a in apps if a["yellow_cards"]]
    assert len(carded) == 1 and carded[0]["minutes_played"] == 80  # jaune : pas de retrait
    assert not any(a["red_cards"] for a in apps)


def test_red_card_removes_player():
    html = _load("match_prod2_red.html").replace("Pro D2", "Top 14")
    _, apps = parse_match(html, "2021-2022")
    reds = [a for a in apps if a["red_cards"]]
    assert reds and all(a["minutes_played"] < 80 for a in reds)


def test_invalid_pages_quarantined():
    with pytest.raises(MatchParseError, match="En-tête"):
        parse_match("<html><body>rien</body></html>", "2024-2025")
    with pytest.raises(MatchParseError, match="hors Top 14"):
        parse_match(_load("match_prod2_red.html"), "2021-2022")
    no_sheet = _load("match_standard.html").replace("fdm", "other")
    with pytest.raises(MatchParseError, match="Feuille"):
        parse_match(no_sheet, "2023-2024")
    no_id = _load("match_standard.html").replace('rel="canonical"', 'rel="x"')
    with pytest.raises(MatchParseError, match="Identifiant"):
        parse_match(no_id, "2023-2024")
