"""Synthetic played rows with a known cloglog hazard (F20 recovery and run tests).

Columns mirror `ml_player_match` for everything `DesignSpec()` reads. The hazard of row i is
h = 1 - exp(-exp(eta + log(minutes/80))), eta = base + beta[unit] * consecutive_matches
+ beta_min28 * (min_28d / 100): the exact data-generating process of the M1 cloglog model.
"""

from datetime import UTC, datetime, timedelta
from typing import Any

import numpy as np
import polars as pl

TEAMS = 14

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
    rest_prob: float = 0.0,
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
    played = rng.random(n) >= rest_prob
    minutes = np.where(played, minutes, 0)
    beta = np.where(unit == "forward", beta_forward, beta_back)
    eta = (
        base
        + beta * consecutive
        + beta_min28 * min_28d / 100
        + np.log(np.where(played, minutes, 80) / 80)
    )
    y = played & (rng.random(n) < 1 - np.exp(-np.exp(eta)))
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
            "team_id": [f"t{i % TEAMS:02d}" for i in player],
            "played": played,
            "minutes_played": minutes.astype(np.int32),
            "y_injury": y,
            "position_code": code,
            "position_group": group,
            "unit": unit,
            "surface": rng.choice(["natural", "hybrid"], size=n),
            "season_period": ["2018_2026"] * n,
            "consecutive_matches": consecutive.astype(np.int32),
            "consecutive_starts": np.maximum(consecutive - rng.integers(0, 2, size=n), 0).astype(
                np.int32
            ),
            "min_7d": np.clip(min_28d // 4 + rng.integers(-20, 20, size=n), 0, None).astype(
                np.int32
            ),
            "min_28d": min_28d.astype(np.int32),
            "apps_20min_365d": rng.integers(0, 30, size=n).astype(np.int32),
            "days_since_last_match": rng.choice([6, 7, 8, 14, 21, 999], size=n).astype(np.int32),
            "season_round_index": match.astype(np.int32),
            "weeks_without_rest": rng.integers(0, 5, size=n).astype(np.int32),
            "age": rng.normal(27, 3, size=n),
            "short_turnaround": rng.random(n) < 0.1,
            "intl_window": rng.random(n) < 0.2,
            "protected_list": rng.random(n) < 0.03,
            "recent_return_8w": rng.random(n) < 0.05,
            "n_prior_injuries_365d": rng.poisson(0.2, size=n).astype(np.int32),
            "days_since_return": rng.integers(0, 400, size=n).astype(np.int32),
            "prior_concussions_365d": rng.poisson(0.05, size=n).astype(np.int32),
            "is_home": rng.random(n) < 0.5,
            "is_playoff": rng.random(n) < 0.03,
            "opponent_strength": rng.random(n),
        }
    )


def selection_frame(  # noqa: PLR0913 - paramètres du processus simulé
    *,
    players: int = 800,
    seasons: int = 2,
    matches: int = 22,
    base: float = -3.4,
    beta_load: float = 0.06,
    gamma_fatigue: float = 0.7,
    sel_a: float = 2.2,
    sel_b: float = 0.20,
    sel_c: float = 0.9,
    seed: int = 0,
) -> pl.DataFrame:
    """Eligible rows (played or not) reproducing the survivor bias corrected by IPW (F21).

    DGP par match :
    - X = consecutive_matches : runs géométriques (proba de poursuite 0,75), indépendantes
      du signal de fatigue ;
    - Z = min_7d : signal de fatigue observé (120 + 60 u + bruit, u ~ N(0,1) latente),
      INDEPENDANT de X dans la population éligible ;
    - sélection : logit pi = sel_a - sel_b X - sel_c Z/100 (le staff aligne les joueurs
      fatigués et fait tourner après les longues séquences) ; played ~ Bernoulli(pi) ;
    - hazard (toutes lignes, 80 min) : cloglog(h) = base + beta_load X + gamma_fatigue Z/100.
      y est généré pour TOUTES les lignes éligibles (y indépendant de played sachant X, Z) :
      la cible du test est le coefficient de X du M1 ajusté sur la population éligible
      entière, que le M1w pondéré doit rejoindre.

    Le biais : `played` est un collider commun de X et Z. Conditionner sur played induit
    Corr(X, Z | joué) < 0 -> le M1 naïf (y ~ X seul, lignes jouées) sous-estime le coefficient
    de X de la population éligible. L'IPW avec pi_hat(X, Z) (features observées -> régression
    logistique bien spécifiée, pente de calibration proche de 1, gate ouvert) restaure la loi
    éligible où X est indépendant de Z.
    """
    rng = np.random.default_rng(seed)
    keys = [
        "player_key",
        "season_id",
        "kickoff_ts",
        "dataset_version",
        "team_id",
        "played",
        "minutes_played",
        "y_injury",
        "position_code",
        "position_group",
        "unit",
        "surface",
        "season_period",
        "consecutive_matches",
        "consecutive_starts",
        "min_7d",
        "min_28d",
        "apps_20min_365d",
        "days_since_last_match",
        "season_round_index",
        "weeks_without_rest",
        "age",
        "short_turnaround",
        "intl_window",
        "protected_list",
        "recent_return_8w",
        "n_prior_injuries_365d",
        "days_since_return",
        "prior_concussions_365d",
        "is_home",
        "is_playoff",
        "opponent_strength",
    ]
    out: dict[str, list[Any]] = {k: [] for k in keys}
    start = datetime(2020, 9, 1, 15, tzinfo=UTC)
    pos_idx = rng.integers(0, len(POSITIONS), size=players)
    u = rng.normal(0, 1, size=players)
    for i in range(players):
        code, group, unit = POSITIONS[pos_idx[i]]
        for s_ in range(seasons):
            consecutive = 0
            for m in range(matches):
                consecutive = consecutive + 1 if rng.random() < 0.75 else 0
                min_7d = int(np.clip(120 + 60 * u[i] + rng.normal(0, 40), 0, 320))
                min_28d = int(np.clip(4 * min_7d + rng.normal(0, 60), 0, 640))
                recent_return = bool(consecutive <= 1 and rng.random() < 0.3)
                logit_pi = sel_a - sel_b * consecutive - sel_c * min_7d / 100
                played = bool(rng.random() < 1 / (1 + np.exp(-logit_pi)))
                eta = base + beta_load * consecutive + gamma_fatigue * min_7d / 100
                y = bool(rng.random() < 1 - np.exp(-np.exp(eta)))
                kickoff = start + timedelta(days=365 * s_ + 7 * m)
                row = {
                    "player_key": f"p{i:04d}",
                    "season_id": f"{2020 + s_}-{2021 + s_}",
                    "kickoff_ts": kickoff,
                    "dataset_version": "synthetic",
                    "team_id": f"t{i % TEAMS:02d}",
                    "played": played,
                    "minutes_played": 80 if played else 0,
                    "y_injury": y,
                    "position_code": code,
                    "position_group": group,
                    "unit": unit,
                    "surface": "natural",
                    "season_period": "2018_2026",
                    "consecutive_matches": consecutive,
                    "consecutive_starts": consecutive,
                    "min_7d": min_7d,
                    "min_28d": min_28d,
                    "apps_20min_365d": int(rng.integers(0, 30)),
                    "days_since_last_match": 7 if consecutive else 999,
                    "season_round_index": m,
                    "weeks_without_rest": min(consecutive // 4, 4),
                    "age": 27.0,
                    "short_turnaround": False,
                    "intl_window": False,
                    "protected_list": False,
                    "recent_return_8w": recent_return,
                    "n_prior_injuries_365d": int(rng.poisson(0.2)),
                    "days_since_return": 200,
                    "prior_concussions_365d": int(rng.poisson(0.05)),
                    "is_home": bool(rng.random() < 0.5),
                    "is_playoff": False,
                    "opponent_strength": float(rng.random()),
                }
                for k in keys:
                    out[k].append(row[k])
    return pl.DataFrame(out)


# Vrais effets par poste (échelle cloglog, écart à l'intercept) du DGP hiérarchique (F22).
TRUE_POSITION_EFFECTS = {
    "PROP": 0.10,
    "HOOKER": 0.35,
    "LOCK": 0.0,
    "BACK_ROW": 0.15,
    "SCRUM_HALF": -0.25,
    "FLY_HALF": -0.15,
    "CENTRE": 0.05,
    "WING": 0.20,
    "FULLBACK": -0.30,
}


def hierarchical_frame(  # noqa: PLR0913 - paramètres du processus simulé
    *,
    players: int = 500,
    seasons: int = 2,
    matches: int = 26,
    alpha: float = -2.6,
    slope_forward: float = 0.15,
    slope_back: float = 0.0,
    sigma_player: float = 0.4,
    sigma_team: float = 0.2,
    rest_prob: float = 0.0,
    seed: int = 0,
) -> pl.DataFrame:
    """M2 DGP: cloglog(h) = alpha + effect[position_code] + slope[unit] * consecutive_std
    + u_player + v_team_season + log(minutes/80). Other covariates of `hazard_frame` have no
    effect. `consecutive_std` = consecutive_matches standardised on the whole frame (the
    design learns the same moments when the whole frame is the training fold)."""
    df = hazard_frame(
        players=players, seasons=seasons, matches=matches, rest_prob=rest_prob, seed=seed
    )
    rng = np.random.default_rng(seed + 1)
    cons = df["consecutive_matches"].to_numpy().astype(float)
    cons_std = (cons - cons.mean()) / cons.std()
    effect = np.array([TRUE_POSITION_EFFECTS[c] for c in df["position_code"]])
    slope = np.where(df["unit"].to_numpy() == "forward", slope_forward, slope_back)
    u = rng.normal(0, sigma_player, size=players)
    player_idx = np.array([int(k[1:]) for k in df["player_key"]])
    team_season = [f"{t}|{s}" for t, s in zip(df["team_id"], df["season_id"], strict=True)]
    levels = sorted(set(team_season))
    v = dict(zip(levels, rng.normal(0, sigma_team, size=len(levels)), strict=True))
    minutes = df["minutes_played"].to_numpy().astype(float)
    played = df["played"].to_numpy()
    eta = (
        alpha
        + effect
        + slope * cons_std
        + u[player_idx]
        + np.array([v[t] for t in team_season])
        + np.log(np.where(played, minutes, 80) / 80)
    )
    y = played & (rng.random(len(df)) < 1 - np.exp(-np.exp(eta)))
    return df.with_columns(pl.Series("y_injury", y))
