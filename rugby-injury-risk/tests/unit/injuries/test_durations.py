import pytest

from rugby_risk.injuries.durations import parse_duration

CASES = [
    ("6 semaines", (42, 42)),
    ("4 à 6 semaines", (28, 42)),
    ("4-6 semaines", (28, 42)),
    ("2 mois", (56, 62)),
    ("3 jours", (3, 3)),
    ("10 à 15 jours", (10, 15)),
    ("quinzaine", (None, None)),  # vague : hors vocabulaire chiffré
    ("quelques jours", (None, None)),
    ("fin de saison", (None, None)),
    ("saison terminée", (None, None)),
    ("8 semaines minimum", (56, 56)),
    (None, (None, None)),
]


@pytest.mark.parametrize(("text", "expected"), CASES)
def test_durations(text, expected):
    assert parse_duration(text) == expected
