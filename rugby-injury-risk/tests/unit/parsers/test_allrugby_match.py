import pytest

from rugby_risk.parsers.allrugby.match import MatchParseError, parse_match

pytestmark = pytest.mark.unit
FIXTURES = "tests/fixtures/allrugby"


def _load(name):
    return open(f"{FIXTURES}/{name}", encoding="utf-8").read()


def test_standard_match():
    match, apps = parse_match(_load("match_standard.html"), "2023-2024")
    assert match["source_match_id"] == "2"
    assert match["season_id"] == "2023-2024"
    assert match["kickoff_time_imputed"] is True  # date seule -> 15:00 Europe/Paris
    assert (
        match["kickoff_ts"].hour == 14 and match["kickoff_ts"].minute == 0
    )  # 15:00 Paris (heure d'hiver)
    assert match["venue_name"] == "Stade Marcel-Michelin, Clermont-Ferrand"
    assert match["home_score"] == 23 and match["away_score"] == 18
    assert len(apps) == 40
    starters = [a for a in apps if a["is_starter"]]
    assert len(starters) == 30 and len(apps) - len(starters) == 10
    bench_unplayed = [a for a in apps if a["shirt_number"] >= 16 and a["minutes_played"] == 0]
    assert len(bench_unplayed) == 5  # non entrés -> 0
    assert all(a["source"] == "allrugby" and a["team_name"] for a in apps)
    viallard = next(a for a in apps if a["player_name"] == "Kevin VIALLARD")
    assert viallard["is_starter"] and viallard["minutes_played"] == 80
    assert viallard["source_player_id"] == "308"


def test_red_card_match():
    match, apps = parse_match(_load("match_red_card.html"), "2024-2025")
    assert match["kickoff_time_imputed"] is False
    assert match["kickoff_ts"].hour == 19 and match["kickoff_ts"].minute == 5  # 21:05 Paris (UTC+2)
    bourgarit = next(a for a in apps if a["player_name"] == "Pierre BOURGARIT")
    assert bourgarit["shirt_number"] == 2 and bourgarit["minutes_played"] == 51
    assert bourgarit["red_cards"] == 1 and bourgarit["yellow_cards"] == 0
    bosch = next(a for a in apps if a["player_name"] == "Facundo BOSCH")
    assert not bosch["is_starter"] and bosch["minutes_played"] == 29
    sotutu = next(a for a in apps if a["player_name"] == "Hoskins SOTUTU")
    assert sotutu["minutes_played"] == 80  # entré au coup d'envoi après le rouge
    assert all(
        a["yellow_cards"] == 0 and a["red_cards"] == 0
        for a in apps
        if a["player_name"] != "Pierre BOURGARIT"
    )


def test_playoff_match():
    match, apps = parse_match(_load("match_playoff.html"), "2024-2025")
    assert match["round"] == "Demi"
    assert match["source_match_id"] == "3"
    assert len(apps) == 40


def test_invalid_pages_quarantined():
    with pytest.raises(MatchParseError):
        parse_match("<html><body>rien</body></html>", "2024-2025")
    html = _load("match_standard.html").replace(
        "ASM Clermont — Clermont-Ferrand", "Autre Club — Ville", 1
    )
    with pytest.raises(MatchParseError):
        parse_match(html, "2024-2025")  # feuille incohérente avec le titre
    non_top14 = _load("match_standard.html").replace("top14", "prod2")
    with pytest.raises(MatchParseError):
        parse_match(non_top14, "2024-2025")
