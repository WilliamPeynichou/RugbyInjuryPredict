from pathlib import Path

import pytest

from rugby_risk.parsers.allrugby.player import PlayerParseError, parse_player

pytestmark = pytest.mark.unit


def test_full_profile():
    profile = parse_player(
        Path("tests/fixtures/allrugby/player_full.html").read_text(encoding="utf-8"), "108"
    )
    assert profile["full_name"] == "Antoine DUPONT"
    assert str(profile["birth_date"]) == "1994-12-14"
    assert profile["height_cm"] == 174
    assert profile["weight_kg"] == 85
    assert profile["nationality"] == "France"
    assert profile["jiff"] is True


def test_partial_profile_no_exception():
    profile = parse_player(
        Path("tests/fixtures/allrugby/player_partial.html").read_text(encoding="utf-8"), "319"
    )
    assert profile["full_name"] == "Louis FOURNIER"
    assert profile["birth_date"] is None
    assert profile["height_cm"] is None
    assert profile["jiff"] is None


def test_invalid_page_quarantined():
    with pytest.raises(PlayerParseError):
        parse_player("<html><body>sans nom</body></html>", "1")
