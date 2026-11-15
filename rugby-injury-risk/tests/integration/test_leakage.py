"""F17 leakage proof: dbt table vs independent Python reference (docs/05 §8), plus mutation test."""

import random
import shutil
from pathlib import Path

import duckdb
import pytest

from rugby_risk.features.reference_impl import Reference
from rugby_risk.features.registry import FEATURES, FLOAT_FEATURES
from tests.factories import build_ml, make_league


def _rows_equal(a: list[tuple[object, ...]], b: list[tuple[object, ...]]) -> bool:
    """Exact sauf FLOAT_FEATURES : tolérance relative 1e-9 (sommation SQL non ordonnée)."""
    if len(a) != len(b):
        return False
    float_idx = [FEATURES.index(c) for c in FLOAT_FEATURES]
    for ra, rb in zip(a, b, strict=True):
        if ra[:2] != rb[:2]:
            return False
        for i, (va, vb) in enumerate(zip(ra[2:], rb[2:], strict=True)):
            if i in float_idx and va is not None and vb is not None:
                if abs(float(va) - float(vb)) > 1e-9 * max(1.0, abs(float(va))):
                    return False
            elif va != vb:
                return False
    return True


pytestmark = pytest.mark.integration

N_COMPARE = 200  # lignes comparées une à une (chaque comparaison est un recalcul complet)


@pytest.fixture(scope="module")
def league_path(tmp_path_factory) -> Path:
    league = make_league(seasons=3, seed=1)
    warehouse = tmp_path_factory.mktemp("leak") / "w.duckdb"
    assert build_ml(warehouse, tmp_path_factory.mktemp("dbt"), league)
    return warehouse


def _compare(con: duckdb.DuckDBPyConnection) -> list[str]:
    ref = Reference(con)
    rows = con.execute(
        f"""select d.player_id, m.match_id, {", ".join(f"m.{c}" for c in FEATURES)}
        from ml_player_match m
        join dim_player d using (player_key)
        order by m.match_id, d.player_id limit {N_COMPARE}"""
    ).fetchall()
    failures: list[str] = []
    for row in rows:
        pid, mid = row[0], row[1]
        expected = ref.features(int(pid), int(mid))
        for name, sql_value in zip(FEATURES, row[2:], strict=True):
            got = expected[name]
            if name in FLOAT_FEATURES:
                ok = (sql_value is None and got is None) or (
                    sql_value is not None
                    and got is not None
                    and abs(float(sql_value) - float(got)) < 1e-6
                )
            else:
                ok = (sql_value is None and got is None) or sql_value == got
            if not ok:
                failures.append(f"match={mid} player={pid} {name}: sql={sql_value!r} ref={got!r}")
                if len(failures) > 10:
                    return failures
    return failures


def test_no_leakage_reference_equality(league_path: Path) -> None:
    with duckdb.connect(str(league_path)) as con:
        failures = _compare(con)
    assert not failures, failures


def test_mutation_future_events_do_not_change_row(league_path: Path, tmp_path: Path) -> None:
    """Modifier minutes/cartons du match t et des matchs postérieurs, et les blessures >= D,
    ne change aucune feature des lignes de t (les cibles, elles, changent)."""
    mutated = tmp_path / "mut.duckdb"
    shutil.copy(league_path, mutated)
    with duckdb.connect(str(mutated)) as con:
        cutoff = con.execute(
            "select max(kickoff_ts) from fact_match where season_id = '2022-2023'"
        ).fetchone()[0]
        con.execute(
            """update fact_appearance set minutes_played = 7, yellow_cards = 3, red_cards = 1
            where match_id in (select match_id from fact_match where kickoff_ts >= ?)""",
            [cutoff],
        )
        con.execute(
            "delete from fact_injury_event where onset_date >= ?::date",
            [cutoff],
        )
        assert build_ml(mutated, tmp_path / "dbt_mut", league=None)
    with (
        duckdb.connect(str(league_path)) as before,
        duckdb.connect(str(mutated)) as after,
    ):
        cols = ", ".join(FEATURES)
        base = (
            f"select player_key, match_id, {cols} from ml_player_match"
            " where kickoff_ts < ? order by player_key, match_id"
        )
        assert _rows_equal(
            before.execute(base, [cutoff]).fetchall(),
            after.execute(base, [cutoff]).fetchall(),
        )
        # Les lignes >= cutoff doivent avoir bougé (sinon le test ne teste rien).
        changed = after.execute(
            "select count(*) from ml_player_match where kickoff_ts >= ?",
            [cutoff],
        ).fetchone()
        assert changed and changed[0] > 0


def test_registry_partition_matches_table(league_path: Path) -> None:
    from rugby_risk.features.export import check_columns  # noqa: PLC0415 - usage ponctuel

    with duckdb.connect(str(league_path)) as con:
        check_columns(con)  # lève MLTableError si colonne hors registre ou nominative


def test_dataset_version_stable(league_path: Path, tmp_path: Path) -> None:
    shutil.copy(league_path, tmp_path / "v.duckdb")
    assert build_ml(tmp_path / "v.duckdb", tmp_path / "dbt_v", league=None)
    with (
        duckdb.connect(str(league_path)) as a,
        duckdb.connect(str(tmp_path / "v.duckdb")) as b,
    ):
        va = a.execute("select any_value(dataset_version) from ml_player_match").fetchone()
        vb = b.execute("select any_value(dataset_version) from ml_player_match").fetchone()
    assert va == vb and va and va[0]


def test_random_sample_deterministic(league_path: Path) -> None:
    """Deux échantillons aléatoires disjoints passent aussi (pas un cas chanceux)."""
    rng = random.Random(7)
    with duckdb.connect(str(league_path)) as con:
        n = con.execute("select count(*) from ml_player_match").fetchone()[0]
        offset = rng.randrange(0, max(n - N_COMPARE, 1))
        ref = Reference(con)
        rows = con.execute(
            f"""select d.player_id, m.match_id, {", ".join(f"m.{c}" for c in FEATURES)}
            from ml_player_match m
            join dim_player d using (player_key)
            order by m.match_id, d.player_id limit {N_COMPARE} offset {offset}"""
        ).fetchall()
        failures = []
        for row in rows:
            expected = ref.features(int(row[0]), int(row[1]))
            for name, sql_value in zip(FEATURES, row[2:], strict=True):
                got = expected[name]
                ok = (
                    abs(float(sql_value) - float(got)) < 1e-6
                    if name in FLOAT_FEATURES and sql_value is not None and got is not None
                    else sql_value == got
                )
                if not ok:
                    failures.append(f"{name}: sql={sql_value!r} ref={got!r}")
                    if len(failures) > 10:
                        break
    assert not failures, failures
