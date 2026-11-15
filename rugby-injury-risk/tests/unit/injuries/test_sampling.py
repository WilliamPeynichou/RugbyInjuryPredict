import duckdb

from rugby_risk.injuries.annotation import draw_sample


def _db() -> duckdb.DuckDBPyConnection:
    con = duckdb.connect(":memory:")
    con.execute(
        """create table fact_injury_event as
           select * from (values
             (1, date '2024-01-10', 'knee', 'match', 0.95, 100, ['exit']),
             (2, date '2024-02-10', null, 'unknown', 0.40, null, ['absence']),
             (3, date '2024-03-10', 'head', 'match', 0.75, 200, ['exit','announcement'])
           ) t(player_id, onset_date, body_region, context, source_confidence,
               onset_match_id, signals)"""
    )
    con.execute(
        """create table fact_match as
           select * from (values (100, '2023-2024', date '2024-01-10'),
                                  (200, '2023-2024', date '2024-03-10'),
                                  (300, '2023-2024', date '2024-04-01'))
           t(match_id, season_id, match_date)"""
    )
    con.execute(
        """create table fact_appearance as
           select * from (values (1, 100, 80), (4, 300, 80), (5, 300, 0))
           t(player_id, match_id, minutes_played)"""
    )
    con.execute(
        """create table int_injury_signal__exit as
           select * from (values (3, 200))
           t(player_id, match_id)"""
    )
    return con


def test_draw_sample_deterministic():
    con = _db()
    a = draw_sample(con, n=6, seed=42)
    b = draw_sample(con, n=6, seed=42)
    assert [(s.episode_kind, s.key) for s in a] == [(s.episode_kind, s.key) for s in b]


def test_stratification_covers_bands_and_non_episodes():
    sample = draw_sample(_db(), n=10, seed=7)
    bands = {s.band for s in sample if s.episode_kind == "episode"}
    assert bands == {"low", "medium", "high"}
    assert any(s.episode_kind == "non_episode" for s in sample)
    keys = [s.key for s in sample]
    assert len(keys) == len(set(keys))
