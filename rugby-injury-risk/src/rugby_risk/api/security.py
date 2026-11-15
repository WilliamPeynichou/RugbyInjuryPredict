"""Garde-fous de réponse (F26) : inspection des clés interdites et en-têtes de cache.

Dernier rempart : le corps sérialisé est inspecté après le routage, à toute profondeur,
donc une route ne peut pas laisser passer une clé ajoutée plus tard aux tables publiques.
"""

from __future__ import annotations

import json
import logging
from collections.abc import AsyncIterator, Awaitable, Callable
from typing import Final

from fastapi import Request, Response
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.responses import JSONResponse

from rugby_risk.serving.guard import FORBIDDEN_PUBLIC_COLUMNS

logger = logging.getLogger("rugby_risk.api.security")

CACHE_MAX_AGE: Final = 3600
HTTP_OK: Final = 200
LEAK_DETAIL: Final = "Erreur interne : réponse publique invalide."
# Documentation générée (schéma OpenAPI) : ses paramètres portent une clé `name` de métadonnée,
# pas une colonne de données. Seules les réponses de données sont inspectées.
DOCUMENTATION_PATHS: Final = frozenset({"/openapi.json", "/docs", "/redoc"})


def contains_forbidden_key(value: object) -> bool:
    """Vrai si une clé de dict, à toute profondeur (dicts et listes), est interdite."""
    if isinstance(value, dict):
        return any(
            str(key).lower() in FORBIDDEN_PUBLIC_COLUMNS or contains_forbidden_key(item)
            for key, item in value.items()
        )
    if isinstance(value, list):
        return any(contains_forbidden_key(item) for item in value)
    return False


async def _read_body(body_iterator: AsyncIterator[bytes]) -> bytes:
    return b"".join([chunk async for chunk in body_iterator])


class PublicGuardMiddleware(BaseHTTPMiddleware):
    """Réponse JSON portant une clé interdite -> 500 et log d'alerte ; sinon inchangée."""

    async def dispatch(
        self, request: Request, call_next: Callable[[Request], Awaitable[Response]]
    ) -> Response:
        response = await call_next(request)
        if request.url.path in DOCUMENTATION_PATHS:
            return response
        if not response.headers.get("content-type", "").startswith("application/json"):
            return response
        iterator: AsyncIterator[bytes] | None = getattr(response, "body_iterator", None)
        if iterator is None:
            raise RuntimeError("Réponse sans flux : inspection impossible")  # jamais silencieux
        body = await _read_body(iterator)
        try:
            payload: object = json.loads(body)
        except ValueError:
            payload = None
        if contains_forbidden_key(payload):
            logger.error(
                "RÉPONSE PUBLIQUE AVEC CLÉ INTERDITE : %s %s", request.method, request.url.path
            )
            return JSONResponse({"detail": LEAK_DETAIL}, status_code=500)
        # Corps relu : on repart du même statut et des mêmes en-têtes, sans content-length.
        headers = {k: v for k, v in response.headers.items() if k.lower() != "content-length"}
        return Response(
            content=body,
            status_code=response.status_code,
            headers=headers,
            media_type=response.media_type,
        )


async def cache_headers(
    request: Request, call_next: Callable[[Request], Awaitable[Response]]
) -> Response:
    """`Cache-Control: public, max-age=3600` sur chaque GET 200."""
    response = await call_next(request)
    if request.method == "GET" and response.status_code == HTTP_OK:
        response.headers["Cache-Control"] = f"public, max-age={CACHE_MAX_AGE}"
    return response
