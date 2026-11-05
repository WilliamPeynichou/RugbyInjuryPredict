"""Synthetic entity-resolution pipeline: 200 players, 30 cross-source duplicates injected.

Truth: each player i has a LNR sheet + an allrugby sheet on the same match (anchor), and
players 0..29 additionally have a World Rugby international sheet (Splink link). Expected:
200 player_ids, recall 1.0, precision 1.0, stable ids across two runs.
"""

from datetime import UTC, date, datetime, timedelta

import duckdb
import polars as pl
import pytest

from rugby_risk.warehouse import staging_frame, write_staging
from tests.integration.test_intl_assets import _materialize

pytestmark = pytest.mark.integration

FIRSTS = [
    "Antoine",
    "Romain",
    "Gregory",
    "Gael",
    "Jean-Baptiste",
    "Bernard",
    "Peter",
    "Sebastien",
    "Thomas",
    "Uini",
    "Mamuka",
    "Handre",
    "Willem",
    "Jonathan",
    "Tamaz",
    "Charles",
    "Matthieu",
    "Cyril",
    "Julien",
    "Damian",
]
LASTS = [
    "Dupont",
    "Le Roux",
    "O'Mahony",
    "Mchedlidze",
    "van der Merwe",
    "Ntamack",
    "Alldritt",
    "Gros",
    "Fickou",
    "Ramos",
]
POSITIONS = ["PROP", "HOOKER", "LOCK", "BACK_ROW"]
CLUB_A = {"lnr": "Stade Toulousain", "allrugby": "Stade Toulousain"}
SID = {"lnr": "L", "allrugby": "A", "worldrugby": "W"}
CLUB_B = {"lnr": "ASM Clermont Auvergne", "allrugby": "ASM Clermont"}
DUPLICATES = 30
PLAYERS = len(FIRSTS) * len(LASTS)  # 200


def _names(i: int) -> tuple[str, str]:
    return FIRSTS[i % len(FIRSTS)], LASTS[i // len(FIRSTS)]


def _seed(tmp_path):
    staging = tmp_path / "data" / "staging"
    matches, appearances, profiles = [], [], []
    truth: dict[str, int] = {}
    kickoff0 = datetime(2024, 2, 2, 20, 5, tzinfo=UTC)
    for i in range(PLAYERS):
        first, last = _names(i)
        home = CLUB_A if i % 2 == 0 else CLUB_B
        away = CLUB_B if i % 2 == 0 else CLUB_A
        day = kickoff0 + timedelta(days=i // 8, hours=0)
        match = {
            "competition_code": "TOP14",
            "season_id": "2023-2024",
            "round": "J10",
            "kickoff_ts": day,
            "kickoff_time_imputed": False,
            "venue_name": "Stade Ernest-Wallon",
            "home_score": 20,
            "away_score": 10,
        }
        for source, mid in (("lnr", f"L{i}"), ("allrugby", f"A{i}")):
            matches.append(
                match
                | {
                    "source": source,
                    "source_match_id": mid,
                    "home_team_name": home[source],
                    "away_team_name": away[source],
                }
            )
            appearances.append(
                {
                    "source": source,
                    "source_match_id": mid,
                    "source_player_id": f"{SID[source]}{i}",
                    "player_name": f"{first} {last}"
                    if source == "lnr"
                    else f"{last.upper()} {first}",
                    "team_name": home[source],
                    "shirt_number": (i % 8) // 2 + 1,  # unique par équipe et par match
                    "is_starter": True,
                    "position_raw": POSITIONS[i % 4],
                    "minutes_played": 80,
                    "yellow_cards": 0,
                    "red_cards": 0,
                }
            )
            profiles.append(
                {
                    "source": source,
                    "source_player_id": f"{SID[source]}{i}",
                    "full_name": f"{first} {last}",
                    "birth_date": date(1995, 1, 1) + timedelta(days=i * 37 % 3000),
                    "height_cm": 180 + i % 20,
                    "weight_kg": 90 + i % 20,
                    "nationality": "France" if source == "allrugby" else None,
                    "jiff": None,
                    "positions_raw": POSITIONS[i % 4],
                }
            )
            truth[f"{source}:{SID[source]}{i}"] = i
    for i in range(DUPLICATES):
        first, last = _names(i)
        matches.append(
            {
                "source": "worldrugby",
                "source_match_id": f"Wm{i}",
                "competition_code": "SIX_NATIONS",
                "season_id": "2023-2024",
                "round": None,
                "kickoff_ts": datetime(2024, 3, 9, 17, 0, tzinfo=UTC),
                "kickoff_time_imputed": False,
                "venue_name": "Stade Fictif",
                "home_team_name": "France",
                "away_team_name": "Ireland",
                "home_score": 27,
                "away_score": 13,
            }
        )
        appearances.append(
            {
                "source": "worldrugby",
                "source_match_id": f"Wm{i}",
                "source_player_id": f"W{i}",
                "player_name": f"{last} {first}",  # ordre inversé, sans accents volontairement
                "team_name": "France",
                "shirt_number": i % 15 + 1,
                "is_starter": True,
                "position_raw": POSITIONS[i % 4],
                "minutes_played": 80,
                "yellow_cards": 0,
                "red_cards": 0,
            }
        )
        profiles.append(
            {
                "source": "worldrugby",
                "source_player_id": f"W{i}",
                "full_name": f"{first} {last}",
                "birth_date": date(1995, 1, 1) + timedelta(days=i * 37 % 3000),
                "height_cm": None,
                "weight_kg": None,
                "nationality": "France",
                "jiff": None,
                "positions_raw": None,
            }
        )
        truth[f"worldrugby:W{i}"] = i
    write_staging(staging_frame("match", matches), "match", "all", "2023-2024", staging)
    write_staging(
        staging_frame("appearance", appearances), "appearance", "all", "2023-2024", staging
    )
    write_staging(
        staging_frame("player_profile", profiles), "player_profile", "all", "2023-2024", staging
    )
    return truth


def _xref(tmp_path) -> pl.DataFrame:
    con = duckdb.connect(str(tmp_path / "warehouse.duckdb"), read_only=True)
    try:
        return pl.from_arrow(con.execute("select * from player_source_xref").to_arrow_table())
    finally:
        con.close()


def test_er_pipeline_synthetic(tmp_path):
    truth = _seed(tmp_path)
    env_extra = {"WAREHOUSE_PATH": str(tmp_path / "warehouse.duckdb"), "ENV": "test"}
    _materialize("player_entities", tmp_path, env_extra=env_extra)
    xref = _xref(tmp_path)
    xref = xref.with_columns(
        pl.concat_str([pl.col("source"), pl.lit(":"), pl.col("source_player_id")]).alias("key")
    )
    ids = dict(zip(xref["key"], xref["player_id"], strict=True))
    # rappel : chaque doublon injecté rejoint son joueur
    linked = sum(ids[f"worldrugby:W{i}"] == ids[f"lnr:L{i}"] for i in range(DUPLICATES))
    assert linked / DUPLICATES >= 0.95
    # précision : deux joueurs distincts ne partagent jamais un player_id
    by_id: dict[int, set[int]] = {}
    for key, player_id in ids.items():
        by_id.setdefault(player_id, set()).add(truth[key])
    assert all(len(players) == 1 for players in by_id.values())
    assert len(by_id) == PLAYERS
    # stabilité : deux runs consécutifs donnent la même xref
    first = xref.sort("key")
    _materialize("player_entities", tmp_path, env_extra=env_extra)
    second = (
        _xref(tmp_path)
        .with_columns(
            pl.concat_str([pl.col("source"), pl.lit(":"), pl.col("source_player_id")]).alias("key")
        )
        .sort("key")
    )
    assert first.select("key", "player_id", "method").equals(
        second.select("key", "player_id", "method")
    )
