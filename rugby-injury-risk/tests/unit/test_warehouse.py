from datetime import UTC, datetime

import duckdb
import polars as pl
import pytest
from pandera.errors import SchemaError

from rugby_risk import warehouse
from rugby_risk.dbt_plugin import Plugin
from rugby_risk.privacy import player_key
from rugby_risk.settings import get_settings

pytestmark = pytest.mark.unit


@pytest.fixture(autouse=True)
def clean(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("ENV", "test")
    get_settings.cache_clear()
    yield
    get_settings.cache_clear()


def _match(**over):
    row = {
        "source": "lnr",
        "source_match_id": "1",
        "competition_code": "TOP14",
        "season_id": "2024-2025",
        "round": None,
        "kickoff_ts": datetime(2025, 1, 1, tzinfo=UTC),
        "venue_name": None,
        "home_team_name": "A",
        "away_team_name": "B",
        "home_score": 10,
        "away_score": 3,
    } | over
    return pl.DataFrame(
        [row],
        schema_overrides={
            "round": pl.String,
            "venue_name": pl.String,
            "kickoff_ts": pl.Datetime(time_zone="UTC"),
        },
    )


def test_write_staging_ok_and_idempotent(tmp_path):
    path = warehouse.write_staging(_match(), "match", "lnr", "2024-2025", root=tmp_path / "s")
    again = warehouse.write_staging(_match(), "match", "lnr", "2024-2025", root=tmp_path / "s")
    assert path == again
    assert "source=lnr/season=2024-2025" in str(path)
    assert pl.read_parquet(path).height == 1


def test_write_staging_default_root():
    path = warehouse.write_staging(_match(), "match", "lnr", "2024-2025")
    assert path.is_relative_to("data/staging")


def test_write_staging_rejects_bad_frame(tmp_path):
    with pytest.raises(SchemaError):
        warehouse.write_staging(_match().drop("home_team_name"), "match", "lnr", "x", root=tmp_path)
    with pytest.raises(ValueError, match="Unknown staging entity"):
        warehouse.write_staging(_match(), "nope", "lnr", "x", root=tmp_path)


def test_upsert_idempotent_and_updates():
    con = warehouse.connect()
    df = pl.DataFrame({"id": [1, 2], "v": ["a", "b"]})
    warehouse.upsert(con, "t", df, ["id"])
    warehouse.upsert(con, "t", df, ["id"])
    warehouse.upsert(con, "t", pl.DataFrame({"id": [2], "v": ["z"]}), ["id"])
    assert con.execute("select id, v from t order by id").fetchall() == [(1, "a"), (2, "z")]


def test_duckdb_player_key_matches_python(monkeypatch):
    monkeypatch.setenv("PSEUDONYM_SALT", "salt")
    get_settings.cache_clear()
    con = duckdb.connect()
    Plugin("p", {}).configure_connection(con)
    assert con.execute("select player_key(42)").fetchone() == (player_key(42, "salt"),)
