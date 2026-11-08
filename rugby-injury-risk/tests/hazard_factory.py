"""Synthetic played rows with a known cloglog hazard (F20 recovery and run tests).

Columns mirror `ml_player_match` for everything `DesignSpec()` reads. The hazard of row i is
h = 1 - exp(-exp(eta + log(minutes/80))), eta = base + beta[unit] * consecutive_matches
+ beta_min28 * (min_28d / 100): the exact data-generating process of the M1 cloglog model.
"""

from datetime import UTC, datetime, timedelta

import numpy as np
import polars as pl

POSITIONS = (
    ("PROP", "front_row", "forward"),
    ("HOOKER", "front_row", "forward"),
    ("LOCK", "lock", "forward"),
    ("BACK_ROW", "back_row", "forward"),
    ("SCRUM_HALF", "half_back", "back"),
    ("FLY_HALF", "half_back", "back"),
    ("CENTRE", "centre", "back"),
    ("WING", "back_three", "back"),
    ("FULLBACK", "back_three", "back"),
)


def hazard_frame(  # noqa: PLR0913 - paramètres du processus simulé
    *,
    players: int = 400,
    seasons: int = 3,
    matches: int = 26,
    base: float = -3.2,
    beta_forward: float = 0.05,
    beta_back: float = 0.0,
    beta_min28: float = 0.0,
    seed: int = 0,
) -> pl.DataFrame:
    rng = np.random.default_rng(seed)
    n = players * seasons * matches
    player = np.repeat(np.arange(players), seasons * matches)
    season = np.tile(np.repeat(np.arange(seasons), matches), players)
    match = np.tile(np.arange(matches), players * seasons)
    pos_idx = rng.integers(0, len(POSITIONS), size=players)[player]
    code = np.array([p[0] for p in POSITIONS])[pos_idx]
    group = np.array([p[1] for p in POSITIONS])[pos_idx]
    unit = np.array([p[2] for p in POSITIONS])[pos_idx]
    consecutive = rng.integers(0, 16, size=n)
    min_28d = rng.integers(0, 321, size=n)
    minutes = rng.integers(20, 81, size=n)
    beta = np.where(unit == "forward", beta_forward, beta_back)
    eta = base + beta * consecutive + beta_min28 * min_28d / 100 + np.log(minutes / 80)
    y = rng.random(n) < 1 - np.exp(-np.exp(eta))
    start = datetime(2020, 9, 1, 15, tzinfo=UTC)
    kickoff = [
        start + timedelta(days=365 * int(s) + 7 * int(m))
        for s, m in zip(season, match, strict=True)
    ]
    return pl.DataFrame(
        {
            "player_key": [f"p{i:04d}" for i in player],
            "season_id": [f"{2020 + s}-{2021 + s}" for s in season],
            "kickoff_ts": kickoff,
            "dataset_version": ["synthetic"] * n,
            "played": [True] * n,
            "minutes_played": minutes.astype(np.int32),
            "y_injury": y,
            "position_code": code,
            "position_group": group,
            "unit": unit,
            "surface": rng.choice(["natural", "hybrid"], size=n),
            "season_period": ["2018_2026"] * n,
            "consecutive_matches": consecutive.astype(np.int32),
            "min_28d": min_28d.astype(np.int32),
            "apps_20min_365d": rng.integers(0, 30, size=n).astype(np.int32),
            "days_since_last_match": rng.choice([6, 7, 8, 14, 21, 999], size=n).astype(np.int32),
            "age": rng.normal(27, 3, size=n),
            "short_turnaround": rng.random(n) < 0.1,
            "intl_window": rng.random(n) < 0.2,
            "recent_return_8w": rng.random(n) < 0.05,
            "n_prior_injuries_365d": rng.poisson(0.2, size=n).astype(np.int32),
            "prior_concussions_365d": rng.poisson(0.05, size=n).astype(np.int32),
            "is_playoff": rng.random(n) < 0.03,
        }
    )
