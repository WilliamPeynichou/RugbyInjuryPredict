import json
from datetime import date
from pathlib import Path

import duckdb
import pytest
from dbt.cli.main import dbtRunner

from rugby_risk.injuries.fusion import Episode, Signal, episode_frame, fuse
from rugby_risk.injuries.priors import incidence_rows, prior_violations
from rugby_risk.injuries.rules import load_rules

pytestmark = pytest.mark.integration


def _episodes() -> list[Episode]:
    rules = load_rules().fusion
    exit_sig = [
        Signal(
            kind="exit",
            player_id=1,
            signal_date=date(2024, 9, 14),
            strength=0.9,
            match_id=1,
            context="match",
        )
    ]
    return fuse(exit_sig, rules)


def _staging(tmp_path: Path) -> Path:
    staging = tmp_path / "staging"
    out = staging / "injury_episode" / "source=fusion" / "season=all"
    out.mkdir(parents=True)
    episode_frame(_episodes()).write_parquet(out / "part.parquet")
    return staging


def test_fact_injury_event_builds_and_tests_pass(tmp_path, monkeypatch):
    warehouse = tmp_path / "dev.duckdb"
    monkeypatch.setenv("WAREHOUSE_PATH", str(warehouse))
    monkeypatch.setenv("ENV", "test")
    staging = _staging(tmp_path)
    common = [
        "--project-dir",
        "dbt",
        "--profiles-dir",
        "dbt",
        "--log-path",
        str(tmp_path / "logs"),
        "--target-path",
        str(tmp_path / "target"),
        "--vars",
        json.dumps({"staging_dir": str(staging), **load_rules().model_dump()}),
    ]
    runner = dbtRunner()
    result = runner.invoke(["build", "--select", "+fact_injury_event", *common])
    assert result.success, [r for r in result.result if r.status == "error"]
    with duckdb.connect(str(warehouse)) as con:
        rows = con.execute(
            "select player_id, onset_date, signals, source_confidence, severity_class"
            " from fact_injury_event"
        ).fetchall()
    assert len(rows) == 1
    player_id, onset, signals, conf, severity = rows[0]
    assert player_id == 1 and str(onset) == "2024-09-14"
    assert signals == ["exit"] and conf == pytest.approx(0.54)
    assert severity == "unknown"


def test_prior_check_warns_outside_range(tmp_path, monkeypatch):
    warehouse = tmp_path / "w.duckdb"
    monkeypatch.setenv("WAREHOUSE_PATH", str(warehouse))
    with duckdb.connect(str(warehouse)) as con:
        con.execute(
            """create table fact_injury_event as select * from (values
               (1, 1, date '2024-09-14', 1, 'match', 'knee', null, false, null, null,
                'unknown', false, 0.9, ['exit'], '{}'::json))
               t(injury_id, player_id, onset_date, onset_match_id, context, body_region,
                 injury_type, is_concussion, return_date, days_missed, severity_class,
                 censored, source_confidence, signals, evidence)"""
        )
        con.execute(
            """create table fact_match as select * from (values
               (1, '2024-2025'))
               t(match_id, season_id)"""
        )
        con.execute(
            """create table fact_appearance as select * from (values
               (1, 1, 1, 80), (1, 2, 1, 80))
               t(match_id, player_id, team_id, minutes_played)"""
        )
        con.execute(
            """create table dim_player as select * from (values
               (1, 'PROP'), (2, 'PROP'))
               t(player_id, position_group)"""
        )
        rows = incidence_rows(con)
        outside = prior_violations(rows)
    # exposition 160 min = 2,67 h ; 1 blessure -> ~375 / 1000 h : très au-dessus de 110
    assert outside and all(r.per_1000h > 110 for r in outside)
