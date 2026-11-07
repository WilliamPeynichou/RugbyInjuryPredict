"""Synthetic league for ML-table tests (F17): marts written directly, injuries at a known rate.

`make_league` returns the mart tables read by `dbt/models/intermediate/int_ml_*`; `load_league`
writes them into a DuckDB warehouse so `dbt run --select int_ml_base+` can build the ML table.
Injured players miss the following team matches until their return date (realistic absences).
"""

import json
import os
import random
import subprocess
import sys
from contextlib import closing
from dataclasses import dataclass, field
from datetime import UTC, date, datetime, timedelta
from pathlib import Path

import duckdb
import polars as pl
from dbt.cli.main import dbtRunner

from rugby_risk.config.seasons import load_seasons
from rugby_risk.injuries.rules import dbt_vars

CLUBS = 6
SQUAD = 26
NATIONAL_TEAM = 100
INTL_PLAYERS = 10
POSITIONS = (
    ("PROP", "front_row", "forward"),
    ("LOCK", "lock", "forward"),
    ("FLY_HALF", "half_back", "back"),
    ("WING", "back_three", "back"),
)


@dataclass
class League:
    matches: list[dict[str, object]] = field(default_factory=list)
    eligibility: list[dict[str, object]] = field(default_factory=list)
    appearances: list[dict[str, object]] = field(default_factory=list)
    players: list[dict[str, object]] = field(default_factory=list)
    injuries: list[dict[str, object]] = field(default_factory=list)


def _kickoff(day: date, hour: int = 19) -> datetime:
    return datetime(day.year, day.month, day.day, hour, tzinfo=UTC)


def _schedule(season_start: int) -> list[tuple[date, str, int, int]]:
    """Double round robin (10 rounds) + 3 national-team tests in February."""
    teams = list(range(1, CLUBS + 1))
    rounds: list[list[tuple[int, int]]] = []
    for _ in range(CLUBS - 1):
        rounds.append([(teams[i], teams[-1 - i]) for i in range(CLUBS // 2)])
        teams = [teams[0], teams[-1], *teams[1:-1]]
    rounds += [[(a, h) for h, a in r] for r in rounds]
    day = date(season_start, 9, 3)
    out: list[tuple[date, str, int, int]] = []
    for i, games in enumerate(rounds):
        # Round 3 is a midweek game (4 days after round 2): short turnarounds exist.
        day += timedelta(days=4 if i == 2 else 7 if i else 0)
        out += [(day, "TOP14", h, a) for h, a in games]
        if i == 4:
            day = date(season_start + 1, 2, 1)
            for k, opp in enumerate((101, 102, 103)):
                out.append((day + timedelta(days=7 * k + 1), "SIX_NATIONS", NATIONAL_TEAM, opp))
            day = date(season_start + 1, 3, 1)
    return out


def make_league(seasons: int = 3, seed: int = 1, p_injury: float = 0.08) -> League:
    rng = random.Random(seed)
    league = League()
    for club in range(1, CLUBS + 1):
        for i in range(SQUAD):
            pid = club * 100 + i
            pos = POSITIONS[i % len(POSITIONS)]
            league.players.append(
                {
                    "player_id": pid,
                    "player_key": f"k{pid}",
                    "full_name": f"Player {pid}",
                    "birth_date": None if i % 7 == 0 else date(1990 + i % 10, 1 + i % 12, 1),
                    "height_cm": None if i % 5 == 0 else 170 + (pid * 7) % 30,
                    "weight_kg": None if i % 6 == 0 else 80 + (pid * 11) % 40,
                    "nationality": "FR",
                    "jiff": True,
                    "primary_position": pos[0],
                    "position_group": pos[1],
                    "unit": pos[2],
                }
            )
    internationals = [club * 100 + i for club in (1, 2) for i in range(INTL_PLAYERS // 2)]
    unavailable_until: dict[int, date] = {}
    match_id = 0
    for s in range(seasons):
        year = 2021 + s
        season_id = f"{year}-{year + 1}"
        for day, comp, home, away in _schedule(year):
            match_id += 1
            league.matches.append(
                {
                    "match_id": match_id,
                    "competition_code": comp,
                    "season_id": season_id,
                    "kickoff_ts": _kickoff(day, 15 if comp == "SIX_NATIONS" else 19),
                    "venue_id": home if comp == "TOP14" else None,
                    "home_team_id": home,
                    "away_team_id": away,
                    "home_score": rng.randint(5, 40),
                    "away_score": rng.randint(5, 40),
                    "is_playoff": False,
                }
            )
            sides = [home, away] if comp == "TOP14" else [NATIONAL_TEAM]
            for team in sides:
                squad = (
                    internationals
                    if team == NATIONAL_TEAM
                    else [team * 100 + i for i in range(SQUAD)]
                )
                fit = [p for p in squad if unavailable_until.get(p, date.min) <= day]
                rng.shuffle(fit)
                sheet = fit[: min(23, len(fit))]
                for pid in squad:
                    row = {"match_id": match_id, "player_id": pid, "team_id": team}
                    if pid not in sheet:
                        league.eligibility.append(row | {"on_sheet": False, "played": False})
                        continue
                    rank = sheet.index(pid)
                    starter = rank < 15
                    minutes = (
                        rng.choice((80, 80, 65, 50))
                        if starter
                        else (0 if rank >= 21 else rng.randint(5, 35))
                    )
                    league.eligibility.append(row | {"on_sheet": True, "played": minutes > 0})
                    league.appearances.append(
                        row
                        | {
                            "is_starter": starter,
                            "minutes_played": minutes,
                            "yellow_cards": int(rng.random() < 0.05),
                            "red_cards": 0,
                        }
                    )
                    if minutes > 0 and rng.random() < p_injury:
                        missed = rng.randint(7, 60)
                        unavailable_until[pid] = day + timedelta(days=missed)
                        league.injuries.append(
                            {
                                "player_id": pid,
                                "onset_date": day,
                                "onset_match_id": match_id,
                                "context": "match",
                                "is_concussion": rng.random() < 0.1,
                                "return_date": day + timedelta(days=missed),
                                "days_missed": missed,
                                "source_confidence": rng.choice((0.75, 0.9)),
                            }
                        )
            if rng.random() < 0.05:
                league.injuries.append(
                    {
                        "player_id": home * 100 + rng.randrange(SQUAD) if comp == "TOP14" else 100,
                        "onset_date": day + timedelta(days=2),
                        "onset_match_id": None,
                        "context": "training",
                        "is_concussion": False,
                        "return_date": None,
                        "days_missed": None,
                        "source_confidence": 0.4,
                    }
                )
    return league


def load_league(con: duckdb.DuckDBPyConnection, league: League) -> None:
    """(Re)create the mart tables read by the ML models."""
    teams = [
        {"team_id": t, "name": f"Team {t}", "is_national": t >= NATIONAL_TEAM}
        for t in [*range(1, CLUBS + 1), NATIONAL_TEAM, 101, 102, 103]
    ]
    tables = {
        "fact_match": league.matches,
        "fact_eligibility": league.eligibility,
        "fact_appearance": league.appearances,
        "dim_player": league.players,
        "fact_injury_event": league.injuries,
        "dim_team": teams,
    }
    for name, rows in tables.items():
        frame = pl.DataFrame(rows, infer_schema_length=None)
        con.register("frame", frame.to_arrow())
        con.execute(f"create or replace table {name} as select * from frame")
        con.unregister("frame")


def build_ml(warehouse: Path, work: Path, league: League | None = None) -> bool:
    """Load `league` (if given) into `warehouse`, then dbt seed + build `int_ml_base+`.

    Sets WAREHOUSE_PATH (absolute) for the in-process dbt runs: the profile default path is
    relative to the dbt project, so without it dbt would create an empty warehouse in dbt/data/.
    """
    warehouse = warehouse.resolve()
    if league is not None:
        with closing(duckdb.connect(str(warehouse))) as con:
            load_league(con, league)
    previous = os.environ.get("WAREHOUSE_PATH")
    os.environ["WAREHOUSE_PATH"] = str(warehouse)
    try:
        subprocess.run([sys.executable, "scripts/export_seeds.py"], check=True)
        common = [
            "--project-dir",
            "dbt",
            "--profiles-dir",
            "dbt",
            "--log-path",
            str(work / "logs"),
            "--target-path",
            str(work / "target"),
            "--vars",
            json.dumps(dbt_vars()),
        ]
        runner = dbtRunner()
        if not runner.invoke(["seed", *common]).success:
            return False
        return bool(runner.invoke(["build", "--select", "int_ml_base+", *common]).success)
    finally:
        if previous is None:
            os.environ.pop("WAREHOUSE_PATH", None)
        else:
            os.environ["WAREHOUSE_PATH"] = previous


REF_TABLES = (
    "competitions",
    "test_windows",
    "rules_protection",
    "protected_players",
    "venue_surface",
)


def load_refs(con: duckdb.DuckDBPyConnection) -> None:
    """ref_* tables straight from data/reference + config/seasons.yaml (no dbt seed)."""
    for name in REF_TABLES:
        path = Path("data/reference") / f"{name}.csv"
        con.execute(
            f"create or replace table ref_{name} as select * from read_csv('{path}',"
            " header = true, nullstr = 'NULL', auto_detect = true)"
        )
    seasons = pl.DataFrame(
        [
            {"season_id": s.season_id, "start_date": s.start_date, "end_date": s.end_date}
            for s in load_seasons()
        ]
    )
    con.register("frame", seasons.to_arrow())
    con.execute("create or replace table ref_seasons as select * from frame")
    con.unregister("frame")
