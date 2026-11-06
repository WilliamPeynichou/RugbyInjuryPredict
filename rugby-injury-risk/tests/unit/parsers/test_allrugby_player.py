import pytest

from rugby_risk.parsers.allrugby.player import PlayerParseError, parse_player

pytestmark = pytest.mark.unit
FIXTURES = "tests/fixtures/allrugby"


def _load(name):
    return open(f"{FIXTURES}/{name}", encoding="utf-8").read()


def test_jiff_player():
    profile = parse_player(_load("player_jiff.html"), "5427")
    assert profile["full_name"] == "Baptiste HÉGUY"
    assert (profile["height_cm"], profile["weight_kg"]) == (196, 108)
    assert profile["nationality"] == "France" and profile["jiff"] is True
    assert profile["positions_raw"] == "3ème ligne"
    assert profile["birth_date"] is None  # allrugby ne donne que l'année


def test_non_jiff_player():
    profile = parse_player(_load("player_non_jiff.html"), "5005")
    assert profile["jiff"] is False and profile["nationality"] == "Australie"


def test_missing_person_quarantined():
    with pytest.raises(PlayerParseError):
        parse_player("<html><body><h1>x</h1></body></html>", "1")
