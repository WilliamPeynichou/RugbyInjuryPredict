"""F16 prior control also reports the ML label subset (confidence >= threshold)."""

import duckdb
import pytest

from rugby_risk.injuries.priors import incidence_markdown, incidence_rows, pooled_rate


@pytest.fixture
def con():
    c = duckdb.connect()
    c.execute(
        """create table fact_injury_event as select * from (values
           (1, 1, 'match', 0.75), (2, 1, 'match', 0.54), (1, 1, 'unknown', 0.4))
           t(player_id, onset_match_id, context, source_confidence)"""
    )
    c.execute("create table fact_match as select 1 as match_id, '2024-2025' as season_id")
    c.execute(
        """create table fact_appearance as select * from (values (1, 1, 600), (1, 2, 600))
           t(match_id, player_id, minutes_played)"""
    )
    c.execute(
        """create table dim_player as select * from (values (1, 'lock'), (2, 'lock'))
           t(player_id, position_group)"""
    )
    yield c
    c.close()


def test_threshold_filters_label_subset(con):
    all_rows = incidence_rows(con)
    label_rows = incidence_rows(con, min_confidence=0.6)
    assert [r.injuries for r in all_rows] == [2]
    assert [r.injuries for r in label_rows] == [1]
    # 20 h d'exposition : 2 -> 100 / 1000 h, 1 -> 50 / 1000 h
    assert pooled_rate(all_rows) == pytest.approx(100.0)
    assert pooled_rate(label_rows) == pytest.approx(50.0)


def test_markdown_has_label_section_only_when_given(con):
    all_rows = incidence_rows(con)
    assert "Label ML" not in incidence_markdown(all_rows)
    md = incidence_markdown(all_rows, incidence_rows(con, min_confidence=0.6), 0.6)
    assert "Label ML `y_injury` (confiance >= 0.6)" in md
    assert "toutes = 100.0 / 1000 h ; label ML = 50.0 / 1000 h" in md


def test_pooled_rate_empty():
    assert pooled_rate([]) is None
