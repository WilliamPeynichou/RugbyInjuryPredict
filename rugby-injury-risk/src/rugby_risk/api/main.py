"""Exposition FastAPI des tables publiques (F26, docs/03 §2.7) : lecture seule, agrégats.

Les données viennent d'un `Repository` : fichiers de prévisualisation (défaut, dev) ou
PostgREST Supabase avec la clé ANONYME (prod). Les routes ne lisent que les tables publiques ;
le middleware inspecte encore chaque réponse JSON.
"""

from __future__ import annotations

from typing import Final

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from rugby_risk.api.deps import (
    PreviewRepository,
    PublicDataUnavailableError,
    Repository,
    SupabaseRepository,
)
from rugby_risk.api.routes import curves, incidence, meta
from rugby_risk.api.schemas import Health
from rugby_risk.api.security import PublicGuardMiddleware, cache_headers
from rugby_risk.settings import Settings, get_settings

API_PREFIX: Final = "/v1"
CORS_METHODS: Final = ["GET"]


def repository_from_settings(settings: Settings) -> Repository:
    """Supabase only with the anonymous key: the service key never reaches the API."""
    anon_key = settings.supabase_anon_key.get_secret_value()
    if settings.supabase_url and anon_key:
        return SupabaseRepository(settings.supabase_url, anon_key)
    return PreviewRepository()


def _origins(raw: str) -> list[str]:
    return [o.strip() for o in raw.split(",") if o.strip()]


async def _unavailable(_request: Request, exc: Exception) -> JSONResponse:
    return JSONResponse(
        status_code=503,
        content={"detail": str(exc)},
    )


def create_app(repository: Repository | None = None, settings: Settings | None = None) -> FastAPI:
    resolved = settings if settings is not None else get_settings()
    app = FastAPI(
        title="Rugby injury risk — agrégats publics (Top 14, par poste)",
        description=(
            "Ordres de grandeur agrégés par poste. Association statistique, non causale ; "
            "cible : blessures avec arrêt d'au moins 2 matchs (sous-déclarées). "
            "Aucune donnée nominative, aucune prédiction individuelle."
        ),
        version="1.0.0",
    )
    app.state.repository = (
        repository if repository is not None else (repository_from_settings(resolved))
    )
    app.add_exception_handler(PublicDataUnavailableError, _unavailable)
    app.add_middleware(
        CORSMiddleware,
        allow_origins=_origins(resolved.front_origin),
        allow_methods=CORS_METHODS,
        allow_headers=[],
        max_age=3600,
    )
    app.add_middleware(PublicGuardMiddleware)
    app.middleware("http")(cache_headers)

    @app.get("/health", response_model=Health, tags=["meta"])
    def health() -> Health:
        return Health()

    app.include_router(meta.router, prefix=API_PREFIX)
    app.include_router(curves.router, prefix=API_PREFIX)
    app.include_router(incidence.router, prefix=API_PREFIX)
    return app


app = create_app()
