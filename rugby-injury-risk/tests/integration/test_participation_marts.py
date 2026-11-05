from datetime import UTC, date, datetime
from pathlib import Path

import duckdb
import polars as pl
import pytest

from rugby_risk.analysis.sequences import write_report
from rugby_risk.calendar import build_calendar
from rugby_risk.marts import build_marts, coverage_markdown, low_quality_seasons
from rugby_risk.warehouse import staging_frame

pytestmark = pytest.mark.integration

SEASON = "2024-2025"
A, B = "Stade Toulousain", "Stade Rochelais"
CLUB = {
    "m1": ("2024-09-07", A, B),
    "m2": ("2024-09-21", B, A),
    "m3": ("2024-10-05", A, B),
    "m4": ("2025-02-08", B, A),
    "m5": ("2025-03-01", A, B),
    "m6": ("2025-03-22", B, A),
}
# (match, source player id, team, shirt, minutes, red cards); q joue aussi France v Ireland.
APPS = [
    ("m1", "a1", A, 1, 80, 0),
    ("m1", "p", A, 10, 80, 0),
    ("m1", "q", B, 15, 80, 0),
    ("m2", "a1", A, 1, 80, 0),
    ("m2", "p", A, 18, 20, 0),
    ("m2", "q", B, 15, 80, 0),
    ("m2", "b1", B, 20, 0, 0),
    ("m3", "q", B, 15, 80, 0),
    ("m4", "a1", A, 1, 80, 0),
    ("m5", "a1", A, 1, 80, 0),
    ("m5", "p", B, 10, 80, 0),
    ("m5", "q", B, 15, 80, 0),
    ("m6", "a1", A, 1, 80, 0),
    ("m6", "p", B, 10, 60, 1),
    ("m6", "q", B, 15, 80, 0),
    ("m6", "b1", B, 20, 20, 0),
]
IDS = {"a1": 1, "p": 2, "q": 3, "b1": 4}


def _kickoff(day: str) -> datetime:
    return datetime.fromisoformat(f"{day}T19:00:00").replace(tzinfo=UTC)


def _match(  # noqa: PLR0913, PLR0917 - fixture row
    source: str, mid: str, comp: str, day: str, home: str, away: str
) -> dict[str, object]:
    return {
        "source": source,
        "source_match_id": mid,
        "competition_code": comp,
        "season_id": SEASON,
        "round": None,
        "kickoff_ts": _kickoff(day),
        "kickoff_time_imputed": False,
        "venue_name": None,
        "home_team_name": home,
        "away_team_name": away,
        "home_score": 20,
        "away_score": 10,
    }


def _app(  # noqa: PLR0913, PLR0917 - fixture row
    source: str, mid: str, pid: str, team: str, shirt: int, minutes: int | None, red: int
) -> dict[str, object]:
    return {
        "source": source,
        "source_match_id": mid,
        "source_player_id": pid,
        "player_name": pid,
        "team_name": team,
        "shirt_number": shirt,
        "is_starter": shirt <= 15,
        "position_raw": "unknown",
        "minutes_played": minutes,
        "yellow_cards": 0,
        "red_cards": red,
    }


def _write(root: Path, entity: str, source: str, frame: pl.DataFrame) -> None:
    out = root / entity / f"source={source}" / f"season={SEASON}" / "part.parquet"
    out.parent.mkdir(parents=True, exist_ok=True)
    frame.write_parquet(out)


@pytest.fixture
def mini_season(tmp_path, monkeypatch):
    warehouse = tmp_path / "w.duckdb"
    monkeypatch.setenv("WAREHOUSE_PATH", str(warehouse))
    monkeypatch.setenv("ENV", "test")
    staging = tmp_path / "staging"
    club = [_match("allrugby", k, "TOP14", d, h, a) for k, (d, h, a) in CLUB.items()]
    intl = [_match("worldrugby", "t1", "SIX_NATIONS", "2025-02-01", "France", "Ireland")]
    matches = staging_frame("match", club + intl)
    _write(staging, "match", "allrugby", staging_frame("match", club))
    _write(staging, "match", "worldrugby", staging_frame("match", intl))
    apps = [_app("allrugby", *row) for row in APPS]
    apps.append(_app("worldrugby", "t1", "wq", "France", 15, None, 0))
    _write(staging, "appearance", "all", staging_frame("appearance", apps))
    calendar, _, unresolved = build_calendar(matches)
    assert not unresolved
    _write(staging, "fixture_calendar", "all", calendar)
    xref = pl.DataFrame(
        {
            "source": ["allrugby"] * 4 + ["worldrugby"],
            "source_player_id": [*IDS, "wq"],
            "player_id": [*IDS.values(), 3],
            "match_confidence": [1.0] * 5,
            "method": ["splink"] * 5,
        }
    )
    dim = pl.DataFrame(
        {"player_id": list(IDS.values()), "player_key": [f"k{i}" for i in IDS.values()]}
    )
    with duckdb.connect(str(warehouse)) as con:
        con.register("x", xref.to_arrow())
        con.execute("create table player_source_xref as select * from x")
        con.register("d", dim.to_arrow())
        con.execute(
            """create table er_dim_player as select player_id, player_key, null::varchar
            as full_name, null::date as birth_date, null::bigint as height_cm, null::bigint
            as weight_kg, null::varchar as nationality, null::boolean as jiff,
            null::varchar as primary_position, null::varchar as position_group,
            null::varchar as unit from d"""
        )
    assert build_marts(staging, tmp_path / "logs", tmp_path / "target")
    with duckdb.connect(str(warehouse)) as con:
        yield con


def _rows(con: duckdb.DuckDBPyConnection, sql: str) -> set[tuple[object, ...]]:
    return set(con.execute(sql).fetchall())


def test_eligibility_matches_expected_line_by_line(mini_season):
    got = _rows(
        mini_season,
        """select (m.kickoff_ts at time zone 'UTC')::date, e.player_id, t.name, e.on_sheet,
        e.played, e.absence_reason from fact_eligibility e join fact_match m using (match_id)
        join dim_team t on t.team_id = e.team_id""",
    )
    day = {k: date.fromisoformat(d) for k, (d, _, _) in CLUB.items()}
    sheet = {(m, IDS[p]): minutes > 0 for m, p, _, _, minutes, _ in APPS}

    def club(pid: int, team: str, keys: list[str]) -> set[tuple[object, ...]]:
        return {
            (day[k], pid, team, (k, pid) in sheet, sheet.get((k, pid), False), None) for k in keys
        }

    expected = (
        club(1, A, list(CLUB))
        | club(2, A, ["m1", "m2"])
        | club(2, B, ["m5", "m6"])
        | club(3, B, list(CLUB))
        | club(4, B, list(CLUB))
        | {(date(2025, 2, 1), 3, "France", True, True, None)}
    )
    assert got == expected


def test_squad_appearance_and_quality(mini_season, tmp_path):
    squad = _rows(
        mini_season,
        """select s.player_id, t.name, s.valid_from, s.valid_to from fact_squad_membership s
        join dim_team t using (team_id) where player_id = 2""",
    )
    assert squad == {
        (2, A, date(2024, 7, 1), date(2024, 9, 21)),
        (2, B, date(2025, 3, 1), date(2025, 6, 30)),
    }
    red = mini_season.execute(
        """select a.position_played, a.minute_on, a.minute_off, a.off_reason
        from fact_appearance a join fact_match m using (match_id)
        where a.player_id = 2 and (m.kickoff_ts at time zone 'UTC')::date = '2025-03-22'"""
    ).fetchone()
    assert red == ("FLY_HALF", 0, 60, "card")
    bench = mini_season.execute(
        "select position_played, minute_on from fact_appearance where shirt_number = 18"
    ).fetchone()
    assert bench == (None, 60)
    # Quelques joueurs par feuille : aucune somme d'équipe dans [1100, 1300] -> saison 'low'.
    assert low_quality_seasons(mini_season) == [SEASON]
    report = coverage_markdown(mini_season)
    assert f"| {SEASON} | TOP14 | 6 | 100.0 | 0.0 |" in report
    assert f"| {SEASON} | SIX_NATIONS | 1 | 0.0 | 0.0 |" in report


def test_sequences_model_and_report(mini_season, tmp_path):
    got = _rows(
        mini_season,
        "select player_id, length, competitions, end_reason from analysis_player_sequences",
    )
    assert got == {
        (1, 2, "TOP14", "absence"),
        (1, 3, "TOP14", "end_of_season"),
        (2, 4, "TOP14", "end_of_season"),
        (3, 4, "SIX_NATIONS,TOP14", "absence"),
        (3, 2, "TOP14", "end_of_season"),
        (4, 1, "TOP14", "end_of_season"),
    }
    report = write_report(mini_season, tmp_path / "reports" / "seq.md").read_text()
    assert "Aucune cellule avec au moins 10 joueurs" in report
