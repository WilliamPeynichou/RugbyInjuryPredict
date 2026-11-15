import json
import subprocess
import sys

import duckdb
import pytest
from dbt.cli.main import dbtRunner

from rugby_risk.injuries.rules import dbt_vars

pytestmark = pytest.mark.integration

SEASON = "2024-2025"
CLUB_DAYS = ["2024-09-07", "2024-09-14", "2024-09-21", "2024-09-28", "2024-10-05"]
INTL_DAY = "2024-09-21"
# player_id: matchs du club où le joueur est sur la feuille
SHEET = {1: [1, 2, 5], 2: [1, 2, 4, 5], 3: [1, 2], 4: [1, 2, 4, 5], 5: [1, 2, 3, 5], 6: [1, 2, 3]}
EXPECTED = {
    1: ("international_duty", 2, False),  # absent pendant le Six Nations d'un international
    2: ("suspension", 1, False),  # rouge au dernier match joué, absence d'un match
    3: ("injury_candidate", 3, True),  # 3 matchs hors fenêtre, jusqu'à la fin de saison
    4: ("protected_rest", 1, False),  # joueur protégé, absence d'un seul match
    5: ("rotation", 1, False),  # absence isolée sans indice
    6: ("injury_candidate", 2, True),  # absence précédée d'un signal de sortie F12 ≥ 0,5
}


@pytest.fixture
def classified(tmp_path, monkeypatch):
    warehouse = tmp_path / "w.duckdb"
    monkeypatch.setenv("WAREHOUSE_PATH", str(warehouse))
    monkeypatch.setenv("ENV", "test")
    with duckdb.connect(str(warehouse)) as con:
        con.execute(
            f"""create table fact_match as select * from (values
            (1, 'TOP14', '{SEASON}', timestamptz '2024-09-07 19:00:00+00'),
            (2, 'TOP14', '{SEASON}', timestamptz '2024-09-14 19:00:00+00'),
            (3, 'TOP14', '{SEASON}', timestamptz '2024-09-21 19:00:00+00'),
            (4, 'TOP14', '{SEASON}', timestamptz '2024-09-28 19:00:00+00'),
            (5, 'TOP14', '{SEASON}', timestamptz '2024-10-05 19:00:00+00'),
            (6, 'SIX_NATIONS', '{SEASON}', timestamptz '2024-09-21 15:00:00+00'))
            t(match_id, competition_code, season_id, kickoff_ts)"""
        )
        con.execute(
            """create table fact_appearance (match_id bigint, player_id bigint, team_id integer,
            is_starter boolean, position_played varchar, minute_off integer, red_cards integer)"""
        )
        rows = [
            (mid, pid, 1, True, "PROP", None, 1 if pid == 2 and mid == 2 else 0)
            for pid, mids in SHEET.items()
            for mid in mids
        ]
        rows.append((6, 1, 2, True, "PROP", None, 0))  # sélection de p1 pendant la fenêtre
        con.executemany("insert into fact_appearance values (?, ?, ?, ?, ?, ?, ?)", rows)
        con.execute(
            """create table fact_eligibility as
            select match_id, player_id, team_id, on_sheet, on_sheet as played,
            null::varchar as absence_reason from (values
            (1, 1, 1, true), (1, 2, 1, true), (1, 3, 1, true), (1, 4, 1, true),
            (1, 5, 1, true), (1, 6, 1, true),
            (2, 1, 1, true), (2, 2, 1, true), (2, 3, 1, true), (2, 4, 1, true),
            (2, 5, 1, true), (2, 6, 1, true),
            (3, 1, 1, false), (3, 2, 1, false), (3, 3, 1, false), (3, 4, 1, false),
            (3, 5, 1, true), (3, 6, 1, true),
            (4, 1, 1, false), (4, 2, 1, true), (4, 3, 1, false), (4, 4, 1, true),
            (4, 5, 1, false), (4, 6, 1, false),
            (5, 1, 1, true), (5, 2, 1, true), (5, 3, 1, false), (5, 4, 1, true),
            (5, 5, 1, true), (5, 6, 1, false), (6, 1, 2, true))
            t(match_id, player_id, team_id, on_sheet)"""
        )
        con.execute(
            """create table dim_team as select * from (values (1, 'Stade Toulousain', false),
            (2, 'France', true)) t(team_id, name, is_national)"""
        )
        con.execute(
            """create table dim_player as select * from (values
            (1, 'k1', 'Un', null, null, null, null, null, 'PROP', 'front_row', 'forward'),
            (2, 'k2', 'Deux', null, null, null, null, null, 'PROP', 'front_row', 'forward'),
            (3, 'k3', 'Trois', null, null, null, null, null, 'PROP', 'front_row', 'forward'),
            (4, 'k4', 'Quatre', null, null, null, null, null, 'PROP', 'front_row', 'forward'),
            (5, 'k5', 'Cinq', null, null, null, null, null, 'PROP', 'front_row', 'forward'),
            (6, 'k6', 'Six', null, null, null, null, null, 'PROP', 'front_row', 'forward'))
            t(player_id, player_key, full_name, birth_date, height_cm, weight_kg, nationality,
              jiff, primary_position, position_group, unit)"""
        )
        con.execute(
            """create table int_injury_signal__exit (match_id bigint, player_id bigint,
            team_id integer, is_starter boolean, position_group varchar, minute_off integer,
            block_change boolean, absent_next boolean, signal_strength double,
            off_reason_derived varchar)"""
        )
        con.execute(
            "insert into int_injury_signal__exit values (3, 6, 1, true, 'front_row', 30,"
            " false, false, 0.8, 'injury_suspected')"
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
    assert runner.invoke(
        ["seed", "--select", "ref_positions ref_test_windows ref_protected_players", *common]
    ).success
    with duckdb.connect(str(warehouse)) as con:
        con.execute(
            "insert into ref_test_windows values ('test_sep_2024', 'Tests sept. 2024',"
            " '2024-09-14', '2024-09-28', 'autumn_tests')"
        )
        con.execute(f"insert into ref_protected_players values ('{SEASON}', 'Quatre', 'http://x')")
    assert runner.invoke(
        [
            "run",
            "--select",
            "int_absence_runs int_eligibility__with_reason fact_unavailability int_absence_report",
            *common,
        ]
    ).success
    with duckdb.connect(str(warehouse)) as con:
        rows = con.execute(
            """select player_id, absence_reason, n_matches, censored_end_of_season
            from int_absence_runs order by player_id"""
        ).fetchall()
        enriched = con.execute(
            """select count(*) from int_eligibility__with_reason
            where not on_sheet and absence_reason is not null"""
        ).fetchone()
        unavail = con.execute("select player_id, reason from fact_unavailability").fetchall()
    return {pid: tuple(rest) for pid, *rest in rows}, enriched[0], unavail


def test_six_synthetic_cases(classified):
    runs, _, _ = classified
    assert set(runs) == set(EXPECTED)
    for pid, (reason, n, censored) in EXPECTED.items():
        assert runs[pid] == (reason, n, censored), pid


def test_enriched_eligibility_and_unavailability(classified):
    _, enriched_count, unavail = classified
    # 1 run de 2 + 1 + 3 + 1 + 1 + 2 = 10 lignes d.absence annotées
    assert enriched_count == 10
    reasons = {pid: reason for pid, reason in unavail}
    assert reasons == {1: "international_duty", 2: "suspension", 4: "protected_rest", 5: "rotation"}


def test_no_international_flagged_injury_without_exit(classified):
    runs, _, _ = classified
    assert runs[1][0] == "international_duty"
