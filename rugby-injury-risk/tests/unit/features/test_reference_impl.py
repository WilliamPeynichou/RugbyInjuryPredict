from datetime import date

import duckdb
import pytest

from rugby_risk.features.reference_impl import Reference
from tests.factories import League, _kickoff, load_league, load_refs

pytestmark = pytest.mark.unit

PID = 101
# (match_id, day, competition, on_sheet, starter, minutes)
GAMES = [
    (1, date(2024, 9, 7), "TOP14", True, True, 80),
    (2, date(2024, 9, 14), "TOP14", True, True, 70),
    (3, date(2024, 9, 18), "TOP14", True, False, 30),
    (4, date(2024, 9, 28), "TOP14", False, False, 0),
    (5, date(2024, 10, 5), "TOP14", True, True, 80),
    (6, date(2024, 11, 9), "AUTUMN_TESTS", True, True, 80),
]


@pytest.fixture
def ref() -> Reference:
    league = League()
    for mid, day, comp, sheet, starter, minutes in GAMES:
        team = 100 if comp == "AUTUMN_TESTS" else 1
        league.matches.append(
            {
                "match_id": mid,
                "competition_code": comp,
                "season_id": "2024-2025",
                "kickoff_ts": _kickoff(day),
                "venue_id": None,
                "home_team_id": team,
                "away_team_id": 2 if team == 1 else 101,
                "home_score": 20 if mid != 4 else 10,
                "away_score": 10 if mid != 4 else 30,
                "is_playoff": False,
            }
        )
        row = {"match_id": mid, "player_id": PID, "team_id": team}
        league.eligibility.append(row | {"on_sheet": sheet, "played": minutes > 0})
        if sheet:
            league.appearances.append(
                row
                | {
                    "is_starter": starter,
                    "minutes_played": minutes,
                    "yellow_cards": 0,
                    "red_cards": 0,
                }
            )
    league.players.append(
        {
            "player_id": PID,
            "player_key": "k",
            "full_name": "X",
            "birth_date": date(2000, 10, 5),
            "height_cm": 180,
            "weight_kg": 81,
            "nationality": "FR",
            "jiff": True,
            "primary_position": "WING",
            "position_group": "back_three",
            "unit": "back",
        }
    )
    for onset, ret, conf in (
        (date(2024, 9, 20), date(2024, 10, 1), 0.9),
        (date(2024, 10, 10), None, 0.9),  # postérieur : jamais visible avant
        (date(2024, 9, 1), None, 0.3),  # sous le seuil
    ):
        league.injuries.append(
            {
                "player_id": PID,
                "onset_date": onset,
                "onset_match_id": None,
                "context": "training",
                "is_concussion": False,
                "return_date": ret,
                "days_missed": (ret - onset).days if ret else None,
                "source_confidence": conf,
            }
        )
    con = duckdb.connect()
    load_league(con, league)
    load_refs(con)
    return Reference(con)


def test_load_and_sequence_before_absence(ref: Reference) -> None:
    f = ref.features(PID, 4)
    assert (f["consecutive_matches"], f["consecutive_starts"], f["consecutive_heavy"]) == (3, 0, 0)
    assert (f["min_7d"], f["min_14d"], f["min_28d"]) == (0, 100, 180)
    assert f["days_since_last_match"] == 10 and f["short_turnaround"] is False
    assert f["n_short_turnarounds_28d"] == 1
    assert f["fge_30d"] == pytest.approx(180 / 80)


def test_absence_breaks_sequence_and_weeks(ref: Reference) -> None:
    f = ref.features(PID, 5)
    assert f["consecutive_matches"] == 0
    assert f["days_since_last_match"] == 17
    assert f["weeks_without_rest"] == 0
    assert ref.features(PID, 3)["weeks_without_rest"] == 2
    assert ref.features(PID, 3)["short_turnaround"] is True


def test_injury_history_uses_only_past(ref: Reference) -> None:
    before_return = ref.features(PID, 4)
    assert before_return["n_prior_injuries_365d"] == 1
    assert before_return["days_missed_365d"] == 8  # jusqu'à D, retour pas encore connu
    assert before_return["days_since_return"] == 999
    after = ref.features(PID, 5)
    assert after["days_missed_365d"] == 11
    assert after["days_since_last_injury"] == 15
    assert after["days_since_return"] == 4 and after["recent_return_8w"] is True
    assert ref.features(PID, 1)["days_since_last_injury"] == 999


def test_international_and_player(ref: Reference) -> None:
    f = ref.features(PID, 6)
    assert f["intl_window"] is True
    assert f["days_since_last_test"] == 999 and f["intl_caps_365d"] == 0
    assert ref.features(PID, 5)["age"] == pytest.approx(24.0, abs=0.01)
    assert f["is_home"] is True and f["competition_code"] == "AUTUMN_TESTS"
    first = ref.features(PID, 1)
    assert first["days_since_last_match_missing"] is True
    assert first["observed_history_days"] == 0
    assert first["opponent_strength_missing"] is True
