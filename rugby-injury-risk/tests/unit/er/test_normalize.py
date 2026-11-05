import pytest

from rugby_risk.entity_resolution.normalize import name_block, normalize_name

pytestmark = pytest.mark.unit

SAME = [
    ("Antoine Dupont", "DUPONT Antoine"),
    ("Grégory Alldritt", "Gregory ALLDRITT"),
    ("Gaël Fickou", "Gael Fickou"),
    ("Jean-Baptiste Gros", "Jean Baptiste Gros"),
    ("Pieter-Steph du Toit", "Pieter Steph Du Toit"),
    ("Bernard Le Roux", "Bernard le Roux Jr"),
    ("Peter O'Mahony", "Peter OMahony"),
    ("Peter O\u2019Mahony", "Peter O'Mahony"),
    ("Sébastien Vahaamahina", "Sebastien VAHAAMAHINA"),
    ("Thomas Ramos", "  thomas   ramos "),
    ("Uini Atonio", "ATONIO Uini"),
    ("Mamuka Gorgodze", "Gorgodze, Mamuka"),
    ("Handré Pollard", "Handre Pollard"),
    ("Willem van der Merwe", "Willem Merwe"),
    ("Danty Jonathan", "Jonathan Danty"),
]


@pytest.mark.parametrize(("left", "right"), SAME)
def test_variants_normalise_identically(left, right):
    assert normalize_name(left) == normalize_name(right)


def test_distinct_players_stay_distinct():
    # Translittérations et diminutifs : laissés à Splink (similarité), pas à la normalisation.
    assert normalize_name("Tamaz Mchedlidze") != normalize_name("Tamazi Mtchedlidze")
    assert normalize_name("Will Skelton") != normalize_name("William Skelton")


def test_block():
    assert name_block(normalize_name("Antoine Dupont")) == "a"
    assert name_block("") == ""
