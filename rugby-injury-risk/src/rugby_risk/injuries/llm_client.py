"""Minimal LLM client (F15): OpenAI-compatible chat, JSON validated, disk cache, retries.

Configurable provider via settings (LLM_BASE_URL / LLM_MODEL / LLM_API_KEY): any
OpenAI-compatible endpoint (OpenAI, Mistral, …). Never call without a human-validated key
and provider (docs/07-legal-rgpd.md): the client raises when the key is empty.
"""

import hashlib
import json
from pathlib import Path
from typing import Any, cast

import httpx
import structlog
from pydantic import BaseModel

from rugby_risk.settings import get_settings

log = structlog.get_logger()

CACHE_DIR = Path("data/staging/_llm_cache")


class LlmUsage(BaseModel):
    """Token usage and estimated cost for one extraction run."""

    documents: int = 0
    cached: int = 0
    prompt_tokens: int = 0
    completion_tokens: int = 0

    @property
    def estimated_cost(self) -> float:
        # Rates are provider-specific; human sets them per run. 0 = not configured.
        return 0.0


def cache_path(doc_id: str, prompt_version: str, model: str) -> Path:
    key = hashlib.sha256(f"{doc_id}|{prompt_version}|{model}".encode()).hexdigest()
    return CACHE_DIR / f"{key}.json"


def _chat(messages: list[dict[str, str]]) -> dict[str, Any]:
    settings = get_settings()
    key = settings.llm_api_key.get_secret_value()
    if not key or not settings.llm_model:
        raise RuntimeError(
            "LLM non configuré : LLM_API_KEY / LLM_MODEL (validation humaine requise, docs/07)"
        )
    with httpx.Client(timeout=120) as client:
        response = client.post(
            f"{settings.llm_base_url.rstrip('/')}/chat/completions",
            headers={"Authorization": f"Bearer {key}"},
            json={"model": settings.llm_model, "messages": messages, "temperature": 0},
        )
        response.raise_for_status()
        return cast(dict[str, Any], response.json())


def extract_json(
    doc_id: str,
    prompt: str,
    prompt_version: str,
    *,
    max_retries: int | None = None,
    usage: LlmUsage | None = None,
) -> dict[str, Any]:
    """Chat completion with JSON output; disk cache on (doc_id, prompt_version, model).

    Retries up to `max_retries` times when the payload is not valid JSON. Returns the
    parsed JSON object (unchecked against the mention schema — see extract.py).
    """
    settings = get_settings()
    retries = settings.llm_max_retries_json if max_retries is None else max_retries
    path = cache_path(doc_id, prompt_version, settings.llm_model)
    if path.exists():
        if usage is not None:
            usage.cached += 1
        log.info("llm_cache_hit", doc_id=doc_id, prompt_version=prompt_version)
        return cast(dict[str, Any], json.loads(path.read_text(encoding="utf-8")))
    payload: dict[str, Any] = {}
    for attempt in range(retries + 1):
        payload = _chat([{"role": "user", "content": prompt}])
        text = (payload.get("choices") or [{}])[0].get("message", {}).get("content", "")
        try:
            parsed = cast(dict[str, Any], json.loads(text))
        except json.JSONDecodeError:
            log.warning("llm_json_invalid", doc_id=doc_id, attempt=attempt)
            if attempt == retries:
                raise
            continue
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(parsed, ensure_ascii=False), encoding="utf-8")
        if usage is not None:
            usage.documents += 1
            usage.prompt_tokens += int((payload.get("usage") or {}).get("prompt_tokens", 0))
            usage.completion_tokens += int((payload.get("usage") or {}).get("completion_tokens", 0))
        return parsed
    raise RuntimeError("unreachable")  # pragma: no cover - loop always returns or raises
