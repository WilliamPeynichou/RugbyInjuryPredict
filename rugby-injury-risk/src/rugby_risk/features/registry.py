"""Column registry of `ml_player_match` (docs/04 §4, docs/05).

Every column of the table belongs to exactly one list (tested). Models build their matrices from
FEATURES_* only: identifiers, targets and exposure (minutes of match t) never enter a model.
Missing-history convention: 999 + `<feature>_missing` flag (days_*), nullable floats + flag.
`travel_km_14d` (docs/05 §6) is not produced: `venues.csv` has no coordinates yet.
"""

from typing import Final

ID_COLUMNS: Final = (
    "player_key",
    "match_id",
    "season_id",
    "team_id",  # F22 : effet aléatoire équipe-saison (club, non nominatif)
    "kickoff_ts",
    "as_of_ts",
    "dataset_version",
)

TARGET_AND_EXPOSURE_COLUMNS: Final = (
    "on_sheet",
    "played",
    "is_starter",
    "minutes_played",
    "y_injury",
    "y_injury_any_7d",
    "y_days_missed",
    "y_injury_conf",
)

FEATURES_CATEGORICAL: Final = (
    "competition_code",
    "position_code",
    "position_group",
    "unit",
    "protection_regime",
    "surface",
    "season_period",
)

FEATURES_NUMERIC: Final = (
    # 1. charge
    "min_7d",
    "min_14d",
    "min_28d",
    "min_56d",
    "min_365d",
    "min_intl_56d",
    "min_club_28d",
    "apps_20min_365d",
    "fge_30d",
    "ewma_acute",
    "ewma_chronic",
    "season_minutes",
    "season_round_index",
    # 2. enchaînement
    "consecutive_matches",
    "consecutive_starts",
    "consecutive_heavy",
    "days_since_last_match",
    "days_since_last_match_missing",
    "short_turnaround",
    "n_short_turnarounds_28d",
    "weeks_without_rest",
    # 3. international et protection
    "intl_window",
    "days_since_last_test",
    "intl_caps_365d",
    "protected_list",
    # 4. antécédents
    "n_prior_injuries_365d",
    "n_prior_injuries_career",
    "days_missed_365d",
    "days_since_last_injury",
    "days_since_return",
    "recent_return_8w",
    "prior_concussions_365d",
    "observed_history_days",
    # 5. individu
    "age",
    "age_missing",
    "height_cm",
    "height_missing",
    "weight_kg",
    "weight_missing",
    "bmi_rel_position",
    "pro_seasons",
    # 6. contexte
    "is_home",
    "is_playoff",
    "month",
    "opponent_strength",
    "opponent_strength_missing",
)

FEATURES: Final = FEATURES_NUMERIC + FEATURES_CATEGORICAL
ALL_COLUMNS: Final = ID_COLUMNS + TARGET_AND_EXPOSURE_COLUMNS + FEATURES
FORBIDDEN_COLUMNS: Final = frozenset(
    {"player_id", "full_name", "player_name", "source_player_id", "birth_date"}
)
# Float features compared with a tolerance in the leakage test (SQL vs Python arithmetic).
FLOAT_FEATURES: Final = frozenset(
    {"fge_30d", "ewma_acute", "ewma_chronic", "age", "bmi_rel_position", "opponent_strength"}
)
NO_HISTORY: Final = 999
INJURY_CONF_THRESHOLD: Final = 0.6
EWMA_HALF_LIVES: Final = {"ewma_acute": 7, "ewma_chronic": 28}
