from datetime import UTC, datetime

import polars as pl
import pytest

from rugby_risk.injuries.extract import run_extraction
from rugby_risk.warehouse import staging_frame

pytestmark = pytest.mark.integration

MENTION = {
    "player_name": "Antoine Dupont",
    "team_name": "Stade Toulousain",
    "onset_date": "2024-11-02",
    "onset_context": "match",
    "opponent_or_match_hint": None,
    "body_region": "knee",
    "injury_type": "ligament",
    "is_concussion": False,
    "announced_duration_text": "4 à 6 semaines",
    "season_ending": False,
    "return_mentioned": True,
    "quote": "forfait quatre à six semaines",
}

DIM = pl.DataFrame(
    {
        "player_id": [1],
        "full_name": ["Antoine Dupont"],
        "primary_position": ["SCRUM_HALF"],
    }
)
SQUAD = pl.DataFrame({"player_id": [1], "team_id": [1], "season_id": ["2024-2025"]})
TEAMS = pl.DataFrame({"team_id": [1, 2], "name": ["Stade Toulousain", "Stade Rochelais"]})
MATCHES = pl.DataFrame(
    {
        "match_id": [11],
        "kickoff_ts": [datetime(2024, 11, 2, 20, 0, tzinfo=UTC)],
        "home_team_id": [1],
        "away_team_id": [2],
    }
)


def _docs(n: int) -> pl.DataFrame:
    return staging_frame(
        "news_doc",
        [
            {
                "doc_id": f"d{i}",
                "url": f"http://x/{i}",
                "published_at": datetime(2024, 11, 5, tzinfo=UTC),
                "title": None,
                "text": f"article {i}",
            }
            for i in range(n)
        ],
    )


def _stub(calls: list[str]):
    def extract_json(doc_id, prompt, version, usage=None):
        calls.append(doc_id)
        return {"mentions": [MENTION]}

    return extract_json


def test_full_pipeline_resolves_player_and_match():
    # aucune mention ambiguë ici : la file de revue (data/review/) n'est pas sollicitée
    calls: list[str] = []
    frame = run_extraction(_docs(2), DIM, SQUAD, TEAMS, MATCHES, _stub(calls), dry_run_limit=None)
    assert len(calls) == 2
    row = frame.row(0, named=True)
    assert row["player_id"] == 1
    assert row["match_id"] == 11
    assert row["needs_review"] is False
    assert (row["announced_duration_days_min"], row["announced_duration_days_max"]) == (28, 42)


def test_dry_run_processes_only_the_limit():
    calls: list[str] = []
    frame = run_extraction(_docs(25), DIM, SQUAD, TEAMS, MATCHES, _stub(calls), dry_run_limit=20)
    assert len(calls) == 20
    assert frame.height == 20
