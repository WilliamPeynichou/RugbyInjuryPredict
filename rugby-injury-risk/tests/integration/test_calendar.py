from datetime import UTC, datetime

import polars as pl
import pytest

from rugby_risk.http.store import RawStore
from rugby_risk.warehouse import staging_frame, write_staging
from tests.integration.test_intl_assets import FIXTURES, _materialize, _put

pytestmark = pytest.mark.integration
SUMMARY = "https://site.api.espn.com/apis/site/v2/sports/rugby/271937/summary"
BOARD = "https://site.api.espn.com/apis/site/v2/sports/rugby/271937/scoreboard?dates=2024"


def _match(source, home, away, kickoff, **extra):
    return {
        "source": source,
        "source_match_id": f"{source}-{home}",
        "competition_code": "TOP14",
        "season_id": "2023-2024",
        "round": "J10" if source == "lnr" else None,
        "kickoff_ts": kickoff,
        "kickoff_time_imputed": False,
        "venue_name": None,
        "home_team_name": home,
        "away_team_name": away,
        "home_score": None,
        "away_score": None,
    } | extra


def _seed(tmp_path):
    store = RawStore(tmp_path / "data" / "raw")
    for event, name in (
        ("910001", "champions_cup_pool"),
        ("910002", "challenge_cup_qf"),
        ("910003", "champions_cup_no_french"),
        ("900001", "rwc_summary"),
    ):
        _put(store, "espn", f"{SUMMARY}?event={event}", FIXTURES / "espn" / f"{name}.json")
    _put(store, "espn", BOARD, FIXTURES / "espn" / "scoreboard_champions_cup.json")
    staging = tmp_path / "data" / "staging"
    paris = datetime(2023, 12, 2, 20, 5, tzinfo=UTC)
    rows = {
        "lnr": [_match("lnr", "Stade Toulousain", "Union Bordeaux Bègles", paris)],
        # allrugby : même match, 3 h d'écart (conflit) ; second match à heure imputée.
        "allrugby": [
            _match(
                "allrugby",
                "Stade Toulousain",
                "Union Bordeaux Bègles",
                datetime(2023, 12, 2, 17, 5, tzinfo=UTC),
                venue_name="Stade Ernest-Wallon, Toulouse",
            ),
            _match(
                "allrugby",
                "ASM Clermont",
                "RC Toulon",
                datetime(2023, 12, 3, 14, 0, tzinfo=UTC),
                kickoff_time_imputed=True,
            ),
        ],
        "espn": [
            _match(
                "espn",
                "Clermont Auvergne",
                "Toulon",
                datetime(2023, 12, 3, 16, 5, tzinfo=UTC),
            ),
        ],
    }
    for source, data in rows.items():
        write_staging(staging_frame("match", data), "match", source, "2023-2024", staging)


def test_calendar_priority_and_conflicts(tmp_path):
    _seed(tmp_path)
    _materialize("europe_staging_espn", tmp_path)
    europe = pl.read_parquet(
        tmp_path / "data/staging/match/source=espn_europe/season=2023-2024/part.parquet"
    )
    assert sorted(europe["source_match_id"].to_list()) == ["910001", "910002"]  # sans club FR exclu
    _materialize("calendar_staging", tmp_path)
    cal = pl.read_parquet(
        tmp_path / "data/staging/fixture_calendar/source=all/season=2023-2024/part.parquet"
    )
    key = [
        "competition_code",
        "season_id",
        "home_team_name",
        "away_team_name",
        pl.col("kickoff_ts").dt.date(),
    ]
    assert not cal.select(key).is_duplicated().any()
    assert cal.height == 5  # 2 Top 14 + poule (summary = scoreboard) + quart + match à venir
    ubb = cal.filter(pl.col("away_team_name") == "Union Bordeaux Bègles").row(0, named=True)
    assert ubb["source"] == "lnr" and ubb["kickoff_ts"] == datetime(2023, 12, 2, 20, 5, tzinfo=UTC)
    assert ubb["round"] == "J10" and ubb["venue_id"] == 1  # stade comblé par allrugby
    toulon = cal.filter(pl.col("away_team_name") == "RC Toulon").row(0, named=True)
    assert toulon["source"] == "espn"  # heure imputée allrugby battue par une heure observée
    conflicts = pl.read_parquet(
        tmp_path / "data/staging/_reports/calendar_conflicts/season=2023-2024.parquet"
    )
    assert conflicts["sources"].to_list() == ["allrugby,lnr"]
