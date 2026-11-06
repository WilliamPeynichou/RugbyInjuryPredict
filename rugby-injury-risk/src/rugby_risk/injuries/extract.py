"""LLM injury-mention extraction pipeline (F15): document -> validated mentions -> staging.

No fusion with other signals here (F16). Never calls a real LLM in tests: `extract_json` is
injected (see llm_client for the real one).
"""

import uuid
from collections.abc import Callable
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

import polars as pl
import structlog
from pydantic import BaseModel, Field

from rugby_risk.injuries.durations import parse_duration
from rugby_risk.injuries.link import link_matches, link_players, write_review_queue
from rugby_risk.injuries.llm_client import LlmUsage
from rugby_risk.injuries.vocab import BodyRegion, InjuryType
from rugby_risk.settings import get_settings
from rugby_risk.warehouse import staging_frame

log = structlog.get_logger()

PROMPT_DIR = Path(__file__).parent / "prompts"
PROMPT_VERSION = "extract_v1"


class InjuryMention(BaseModel):
    player_name: str
    team_name: str | None = None
    onset_date: datetime | None = None
    onset_context: Literal["match", "training", "unknown"] = "unknown"
    opponent_or_match_hint: str | None = None
    body_region: BodyRegion | None = None
    injury_type: InjuryType | None = None
    is_concussion: bool = False
    announced_duration_text: str | None = None
    season_ending: bool = False
    return_mentioned: bool = False
    quote: str = Field(default="", max_length=200)


class ExtractionResult(BaseModel):
    mentions: list[InjuryMention] = Field(default_factory=list)


def load_prompt(version: str = PROMPT_VERSION) -> str:
    return (PROMPT_DIR / f"{version}.md").read_text(encoding="utf-8")


def run_extraction(  # noqa: PLR0913, PLR0917 - pipeline wiring
    documents: pl.DataFrame,
    dim_player: pl.DataFrame,
    squad: pl.DataFrame,
    teams: pl.DataFrame,
    matches: pl.DataFrame,
    extract_json: Callable[..., dict[str, Any]],
    *,
    prompt_version: str = PROMPT_VERSION,
    usage: LlmUsage | None = None,
    dry_run_limit: int | None = None,
) -> pl.DataFrame:
    """Extract injury mentions from press documents into the `injury_mention` staging frame.

    `documents`: news_doc staging frame. `extract_json`: callable(doc_id, prompt,
    prompt_version, usage=...) -> parsed JSON (llm_client.extract_json in production, a
    stub in tests). Ambiguous player attachments go to the review queue on disk.
    """
    template = load_prompt(prompt_version)
    docs = documents.to_dicts()
    if dry_run_limit is not None:
        docs = docs[:dry_run_limit]
    published = {str(d["doc_id"]): d["published_at"].date() for d in docs}
    rows: list[dict[str, Any]] = []
    model = get_settings().llm_model or "simulated"
    for doc in docs:
        prompt = template.replace("{published_at}", str(doc["published_at"])[:10]).replace(
            "{article}", str(doc["text"])
        )
        try:
            parsed = extract_json(str(doc["doc_id"]), prompt, prompt_version, usage=usage)
            result = ExtractionResult.model_validate(parsed)
        except Exception as exc:
            log.warning("llm_extract_failed", doc_id=doc["doc_id"], error=str(exc))
            continue
        for mention in result.mentions:
            days_min, days_max = parse_duration(mention.announced_duration_text)
            rows.append(
                {
                    "mention_id": str(
                        uuid.uuid5(
                            uuid.NAMESPACE_URL,
                            f"{doc['doc_id']}:{mention.quote}:{mention.player_name}",
                        )
                    ),
                    "doc_id": str(doc["doc_id"]),
                    "player_name": mention.player_name,
                    "team_name": mention.team_name,
                    "player_id": None,
                    "match_id": None,
                    "onset_date": mention.onset_date.date() if mention.onset_date else None,
                    "onset_context": mention.onset_context,
                    "body_region": str(mention.body_region) if mention.body_region else None,
                    "injury_type": str(mention.injury_type) if mention.injury_type else None,
                    "is_concussion": mention.is_concussion,
                    "announced_duration_days_min": days_min,
                    "announced_duration_days_max": days_max,
                    "season_ending": mention.season_ending,
                    "return_mentioned": mention.return_mentioned,
                    "quote": mention.quote or None,
                    "needs_review": False,
                    "extraction_model": model,
                    "prompt_version": prompt_version,
                    "extracted_at": datetime.now(UTC),
                }
            )
    frame = staging_frame("injury_mention", rows)
    frame = link_players(frame, dim_player, squad, teams, published)
    frame = link_matches(frame, matches, teams, published)
    review = frame.filter(pl.col("needs_review")).to_dicts()
    if review:
        write_review_queue(review)
        log.info("news_review_queue", n=len(review))
    return frame


def usage_report(usage: LlmUsage) -> str:
    """Small Markdown usage/cost report (tokens per run; cost stays 0 until rates are set)."""
    return (
        "# Utilisation LLM (F15)\n\n"
        f"- documents traités : {usage.documents}\n"
        f"- servis par le cache : {usage.cached}\n"
        f"- tokens prompt : {usage.prompt_tokens}\n"
        f"- tokens complétion : {usage.completion_tokens}\n"
        f"- coût estimé : {usage.estimated_cost:.4f} (taux non configurés = 0)\n"
    )
