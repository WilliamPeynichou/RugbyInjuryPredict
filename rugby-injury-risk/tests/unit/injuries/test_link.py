from datetime import UTC, date, datetime

import polars as pl

from rugby_risk.injuries.link import link_matches, link_players, write_review_queue

DIM = pl.DataFrame(
    {
        "player_id": [1, 2, 3],
        "full_name": ["Antoine Dupont", "Antoine Dupont", "Antoine Dupont"],
        "primary_position": ["SCRUM_HALF"] * 3,
    }
)
SQUAD = pl.DataFrame(
    {
        "player_id": [1, 2, 3],
        "team_id": [1, 2, 3],
        "season_id": ["2024-2025"] * 3,
    }
)
TEAMS = pl.DataFrame(
    {"team_id": [1, 2, 3, 9], "name": ["Stade Toulousain", "Stade Rochelais", "France", "ASM"]}
)
MENTIONS = pl.DataFrame(
    {
        "doc_id": ["d1", "d2", "d3"],
        "player_name": ["Antoine Dupont", "Antoine Dupont", "Antoine Dupont"],
        "team_name": ["Stade Toulousain", None, "Stade Rochelais"],
        "onset_date": [date(2024, 11, 2), None, None],
        "onset_context": ["match", "unknown", "unknown"],
        "quote": ["a", "b", "c"],
    }
)
PUBLISHED = {"d1": date(2024, 11, 5), "d2": date(2024, 11, 5), "d3": date(2024, 11, 5)}


def test_link_players_exact_team_restricted():
    out = link_players(MENTIONS, DIM, SQUAD, TEAMS, PUBLISHED)
    by_doc = dict(zip(out["doc_id"].to_list(), out["player_id"].to_list(), strict=True))
    # l'équipe lève l'ambiguïté entre les homonymes ; sans équipe -> file de revue
    assert by_doc == {"d1": 1, "d2": None, "d3": 2}
    review = dict(zip(out["doc_id"].to_list(), out["needs_review"].to_list(), strict=True))
    assert review == {"d1": False, "d2": True, "d3": False}


def test_link_players_season_scopes_squad():
    squad_other = SQUAD.with_columns(pl.lit("2020-2021").alias("season_id"))
    out = link_players(MENTIONS, DIM, squad_other, TEAMS, PUBLISHED)
    assert out["player_id"].to_list() == [None, None, None]


def test_link_matches_nearest_before_publication():
    matches = pl.DataFrame(
        {
            "match_id": [11, 12, 13],
            "kickoff_ts": [
                datetime(2024, 11, 2, 20, tzinfo=UTC),
                datetime(2024, 11, 1, 20, tzinfo=UTC),
                datetime(2024, 10, 20, 20, tzinfo=UTC),
            ],
            "home_team_id": [1, 1, 1],
            "away_team_id": [2, 2, 2],
        }
    )
    mentions = MENTIONS.with_columns(pl.Series("player_id", [1, None, None], dtype=pl.Int64))
    out = link_matches(mentions, matches, TEAMS, PUBLISHED)
    assert out["match_id"].to_list() == [11, None, None]


def test_write_review_queue_appends(tmp_path):
    rows = [
        {"doc_id": "d1", "player_name": "X", "team_name": None, "onset_date": None, "quote": "q"}
    ]
    path = write_review_queue(rows, tmp_path / "queue.csv")
    write_review_queue(rows, tmp_path / "queue.csv")
    lines = path.read_text(encoding="utf-8").strip().splitlines()
    assert lines[0].startswith("doc_id,") and len(lines) == 3
