from datetime import UTC, datetime

import polars as pl
import pytest
from pydantic import ValidationError

from rugby_risk.injuries import llm_client
from rugby_risk.injuries.extract import ExtractionResult, run_extraction
from rugby_risk.injuries.llm_client import LlmUsage
from rugby_risk.settings import get_settings
from rugby_risk.warehouse import staging_frame

NOW = datetime(2024, 11, 5, tzinfo=UTC)
DOCS = staging_frame(
    "news_doc",
    [
        {
            "doc_id": "d1",
            "url": "http://x/1",
            "published_at": NOW,
            "title": "t",
            "text": "Dupont forfait six semaines.",
        },
        {
            "doc_id": "d2",
            "url": "http://x/2",
            "published_at": NOW,
            "title": None,
            "text": "Rien.",
        },
    ],
)
EMPTY = {name: pl.DataFrame() for name in ("dim_player", "squad", "teams", "matches")}
EMPTY["dim_player"] = pl.DataFrame(
    schema={"player_id": pl.Int64, "full_name": pl.String, "primary_position": pl.String}
)
EMPTY["teams"] = pl.DataFrame(schema={"team_id": pl.Int64, "name": pl.String})
EMPTY["squad"] = pl.DataFrame(
    schema={"player_id": pl.Int64, "team_id": pl.Int64, "season_id": pl.String}
)
EMPTY["matches"] = pl.DataFrame(
    schema={
        "match_id": pl.Int64,
        "kickoff_ts": pl.Datetime(time_zone="UTC"),
        "home_team_id": pl.Int64,
        "away_team_id": pl.Int64,
    }
)

MENTION = {
    "player_name": "Antoine Dupont",
    "team_name": "Stade Toulousain",
    "onset_date": "2024-11-02",
    "onset_context": "match",
    "opponent_or_match_hint": None,
    "body_region": "knee",
    "injury_type": "ligament",
    "is_concussion": False,
    "announced_duration_text": "6 semaines",
    "season_ending": False,
    "return_mentioned": True,
    "quote": "forfait six semaines",
}


def _stub(payload):
    calls = []

    def extract_json(doc_id, prompt, version, usage=None):
        calls.append(doc_id)
        if callable(payload):
            return payload(doc_id)
        return payload

    extract_json.calls = calls
    return extract_json


def test_run_extraction_on_frozen_json(tmp_path, monkeypatch):
    stub = _stub({"mentions": [MENTION]})
    frame = run_extraction(DOCS, **EMPTY, extract_json=stub)
    # d1 : une mention ; d2 : aucune
    assert frame.height == 2
    row = frame.filter(pl.col("doc_id") == "d1").row(0, named=True)
    assert row["announced_duration_days_min"] == 42
    assert row["announced_duration_days_max"] == 42
    assert row["onset_context"] == "match"
    assert row["needs_review"] is True  # aucun joueur dans dim_player
    assert stub.calls == ["d1", "d2"]


def test_invalid_document_skipped_not_fatal():
    stub = _stub(lambda doc_id: (_ for _ in ()).throw(ValidationError.from_exception_data("x", [])))
    frame = run_extraction(DOCS, **EMPTY, extract_json=stub)
    assert frame.is_empty()


def test_mention_schema_rejects_bad_enum():
    bad = {**MENTION, "body_region": "genou"}
    with pytest.raises(ValidationError):
        ExtractionResult.model_validate({"mentions": [bad]})


def test_llm_cache_avoids_second_call(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_client, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(get_settings(), "llm_model", "test-model")
    calls = []

    def fake_chat(messages):
        calls.append(messages)
        return {"choices": [{"message": {"content": '{"mentions": []}'}}], "usage": {}}

    monkeypatch.setattr(llm_client, "_chat", fake_chat)
    usage = LlmUsage()
    first = llm_client.extract_json("d1", "prompt", "v1", usage=usage)
    second = llm_client.extract_json("d1", "prompt", "v1", usage=usage)
    assert first == second == {"mentions": []}
    assert len(calls) == 1
    assert usage.documents == 1 and usage.cached == 1


def test_llm_retries_on_invalid_json(tmp_path, monkeypatch):
    monkeypatch.setattr(llm_client, "CACHE_DIR", tmp_path)
    monkeypatch.setattr(get_settings(), "llm_model", "test-model")
    responses = iter(["not json", '{"mentions": []}'])
    monkeypatch.setattr(
        llm_client,
        "_chat",
        lambda messages: {"choices": [{"message": {"content": next(responses)}}]},
    )
    assert llm_client.extract_json("d2", "p", "v1") == {"mentions": []}
    # épuisé : toutes les réponses invalides -> exception
    monkeypatch.setattr(
        llm_client, "_chat", lambda messages: {"choices": [{"message": {"content": "nope"}}]}
    )
    with pytest.raises(Exception):  # noqa: B017 - JSONDecodeError remontée après retries
        llm_client.extract_json("d3", "p", "v1", max_retries=1)
