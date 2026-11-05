from datetime import UTC, datetime, timedelta
from pathlib import Path

import duckdb
import jinja2
import polars as pl

from rugby_risk.analysis.sequences import build_report, load_stats, sequence_stats

MACRO = Path("dbt/macros/consecutive_run_id.sql").read_text(encoding="utf-8")


def _run_lengths(played: list[bool]) -> list[int]:
    """Render the dbt macro (plain Jinja) and run it on DuckDB: the only sequence logic."""
    window = jinja2.Template(
        MACRO + "{{ consecutive_run_id('player_id', 'round', 'played') }}"
    ).render()
    con = duckdb.connect()
    con.execute("create table t (player_id int, round int, played boolean)")
    con.executemany("insert into t values (1, ?, ?)", list(enumerate(played, start=1)))
    rows = con.execute(
        f"""with r as (select *, {window} as run_id from t)
        select count(*) from r where played group by run_id order by min(round)"""
    ).fetchall()
    return [n for (n,) in rows]


def test_bench_unused_breaks_sequence():
    # J1-J5 joués, J6 banc non entré, J7-J9 joués.
    assert _run_lengths([True] * 5 + [False] + [True] * 3) == [5, 3]


def test_leading_and_repeated_misses():
    assert _run_lengths([False, False, True, False, True, True]) == [1, 2]


def _seqs(position: str, n_players: int, length: int) -> list[dict[str, object]]:
    start = datetime(2024, 9, 7, tzinfo=UTC)
    return [
        {
            "player_id": f"{position}{i}",
            "season_id": "2024-2025",
            "position_code": position,
            "start_ts": start,
            "length": length + i % 3,
        }
        for i in range(n_players)
    ]


def test_sequence_stats_median_p90_max():
    stats = sequence_stats(pl.DataFrame(_seqs("PROP", 10, 4)), ["position_code"])
    row = stats.row(0, named=True)
    assert (row["n_players"], row["median_length"], row["max_length"]) == (10, 5.0, 6)


def test_load_stats_short_turnaround_and_heavy_starts():
    kick = datetime(2024, 9, 7, tzinfo=UTC)
    apps = pl.DataFrame(
        {
            "player_id": [1, 1, 1],
            "season_id": ["2024-2025"] * 3,
            "position_code": ["LOCK"] * 3,
            "kickoff_ts": [kick, kick + timedelta(days=4), kick + timedelta(days=11)],
            "is_starter": [True, True, False],
            "minutes_played": [80, 50, 20],
            "played": [True, True, True],
        }
    )
    row = load_stats(apps).row(0, named=True)
    assert row["median_season_minutes"] == 150
    assert row["mean_short_turnarounds"] == 1
    assert row["share_starts_60"] == 0.5


def test_report_has_tables_and_figures(tmp_path):
    seqs = pl.DataFrame(_seqs("PROP", 12, 3))
    apps = pl.DataFrame(
        schema={
            "player_id": pl.String,
            "season_id": pl.String,
            "position_code": pl.String,
            "kickoff_ts": pl.Datetime(time_zone="UTC"),
            "is_starter": pl.Boolean,
            "minutes_played": pl.Int64,
            "played": pl.Boolean,
        }
    )
    report = build_report(seqs, apps, tmp_path / "figures")
    assert "| PROP | 12 |" in report
    assert len(list((tmp_path / "figures").glob("*.png"))) == 3


def test_report_without_data(tmp_path):
    assert "Aucune séquence" in build_report(pl.DataFrame(), pl.DataFrame(), tmp_path)
