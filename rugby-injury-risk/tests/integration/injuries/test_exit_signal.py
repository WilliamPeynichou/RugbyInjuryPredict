import json
import subprocess
import sys

import duckdb
import pytest
from dbt.cli.main import dbtRunner

from rugby_risk.injuries.rules import dbt_vars

pytestmark = pytest.mark.integration

# player_id: (position, starter, minute_off); tous dans l'équipe 1 au match 1.
APPS = {
    1: ("PROP", True, 50),  # pilier sorti 50e : pas de signal
    2: ("WING", True, 25),  # ailier sorti 25e : signal
    3: ("PROP", False, 70),  # remplaçant entré 55e, sorti 70e : signal fort
    4: ("PROP", True, 52),  # trois avants à la 52e : seuil avants dépassé, pas de signal
    5: ("HOOKER", True, 52),
    6: ("PROP", True, 52),
    7: ("BACK_ROW", True, 42),  # trois 3es lignes à la 42e : bloc, signal faible
    8: ("BACK_ROW", True, 42),
    9: ("BACK_ROW", True, 42),
    10: ("CENTRE", True, 30),  # sorti 30e, absent au match suivant : signal renforcé
}
EXPECTED = {2: 0.7, 3: 0.9, 7: 0.21, 8: 0.21, 9: 0.21, 10: 0.9}


@pytest.fixture
def signals(tmp_path, monkeypatch):
    warehouse = tmp_path / "w.duckdb"
    monkeypatch.setenv("WAREHOUSE_PATH", str(warehouse))
    monkeypatch.setenv("ENV", "test")
    with duckdb.connect(str(warehouse)) as con:
        con.execute(
            """create table fact_match as select * from (values
            (1, timestamptz '2024-09-07 19:00:00+00'), (2, timestamptz '2024-09-14 19:00:00+00'))
            t(match_id, kickoff_ts)"""
        )
        con.execute(
            """create table fact_appearance (match_id bigint, player_id bigint, team_id integer,
            is_starter boolean, position_played varchar, minute_off integer, off_reason varchar)"""
        )
        con.executemany(
            "insert into fact_appearance values (1, ?, 1, ?, ?, ?, 'unknown')",
            [(pid, starter, pos, minute) for pid, (pos, starter, minute) in APPS.items()],
        )
        con.execute(
            """create table fact_eligibility as select * from (values
            (1, 2, 1, true), (1, 10, 1, true), (2, 2, 1, true), (2, 10, 1, false))
            t(match_id, player_id, team_id, on_sheet)"""
        )
    subprocess.run([sys.executable, "scripts/export_seeds.py"], check=True)
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
        json.dumps(dbt_vars()),
    ]
    runner = dbtRunner()
    assert runner.invoke(["seed", "--select", "ref_positions", *common]).success
    assert runner.invoke(["run", "--select", "int_injury_signal__exit", *common]).success
    with duckdb.connect(str(warehouse)) as con:
        rows = con.execute(
            """select player_id, signal_strength, off_reason_derived, block_change, absent_next
            from int_injury_signal__exit"""
        ).fetchall()
    return {pid: rest for pid, *rest in rows}


def test_five_synthetic_cases(signals):
    assert set(signals) == set(EXPECTED)
    for pid, strength in EXPECTED.items():
        assert float(signals[pid][0]) == pytest.approx(strength, abs=0.01), pid


def test_suspected_flag_block_and_next_absence(signals):
    assert signals[2][1] == "injury_suspected"
    assert signals[7][1:] == ["unknown", True, False]
    assert signals[10][1:] == ["injury_suspected", False, True]
