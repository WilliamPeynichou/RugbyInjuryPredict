"""F17 : the ML table built from the synthetic league has the expected shape and prevalence."""

import duckdb
import pytest

from rugby_risk.features.registry import FORBIDDEN_COLUMNS
from tests.factories import build_ml, make_league

pytestmark = pytest.mark.integration

P_INJURY = 0.08


@pytest.fixture(scope="module")
def league():
    return make_league(seasons=3, seed=1)


@pytest.fixture(scope="module")
def warehouse(tmp_path_factory, league):
    path = tmp_path_factory.mktemp("mltable") / "w.duckdb"
    assert build_ml(path, tmp_path_factory.mktemp("dbt"), league)
    return path


def test_row_count_equals_eligibility(warehouse, league) -> None:
    with duckdb.connect(str(warehouse)) as con:
        n = con.execute("select count(*) from ml_player_match").fetchone()
    assert n is not None and n[0] == len(league.eligibility)


def test_prevalence_matches_injected_rate(warehouse) -> None:
    with duckdb.connect(str(warehouse)) as con:
        played, injured = con.execute(
            "select sum(played::integer), sum(y_injury::integer) from ml_player_match"
        ).fetchone()
    assert played and injured is not None
    assert abs(injured / played - P_INJURY) < 0.10


def test_no_identifying_column(warehouse) -> None:
    with duckdb.connect(str(warehouse)) as con:
        columns = {r[0] for r in con.execute("describe ml_player_match").fetchall()}
    assert not columns & FORBIDDEN_COLUMNS


def test_unique_grain(warehouse) -> None:
    with duckdb.connect(str(warehouse)) as con:
        dupes = con.execute(
            """select count(*) from (
               select player_key, match_id from ml_player_match
               group by 1, 2 having count(*) > 1)"""
        ).fetchone()
    assert dupes == (0,)


def test_known_scenarios_present(warehouse) -> None:
    """Short turnarounds and international windows actually occur in the synthetic league."""
    with duckdb.connect(str(warehouse)) as con:
        short, windows, caps = con.execute(
            """select sum(short_turnaround::integer), sum(intl_window::integer),
              sum((intl_caps_365d > 0)::integer) from ml_player_match"""
        ).fetchone()
    assert short and windows and caps and short > 0 and windows > 0 and caps > 0
