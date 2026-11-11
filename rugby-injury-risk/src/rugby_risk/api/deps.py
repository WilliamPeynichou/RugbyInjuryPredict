"""Accès aux données de l'API publique (F26) : fichiers de prévisualisation ou Supabase.

Les deux implémentations renvoient des DataFrames polars et ne lisent que les quatre tables
publiques. Le dépôt Supabase utilise la clé ANONYME ; la clé service n'est jamais passée.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from pathlib import Path
from typing import Annotated, Any, Final, Protocol

import httpx
import polars as pl
from fastapi import Depends, Request

from rugby_risk.serving.export import DRY_RUN_DIR
from rugby_risk.serving.guard import make_public

Record = dict[str, Any]
NOT_AGGREGATED: Final = frozenset({"model_registry_public"})
HTTP_TIMEOUT_S: Final = 30.0
HTTP_ERROR_FROM: Final = 400


class PublicDataUnavailableError(RuntimeError):
    """Tables publiques non joignables (fichier absent, Supabase en panne, table absente)."""


def clean_rows(df: pl.DataFrame) -> list[Record]:
    """NaN -> None : JSON ne connaît pas NaN, une métrique manquante reste manquante."""
    return [{k: _clean(v) for k, v in row.items()} for row in df.iter_rows(named=True)]


def _clean(value: Any) -> Any:
    if isinstance(value, float) and math.isnan(value):
        return None
    return value


class Repository(Protocol):
    """Lecture seule des tables publiques, par nom."""

    def table(self, name: str) -> pl.DataFrame: ...


@dataclass(frozen=True)
class PreviewRepository:
    """Export déterministe du dry-run (`rugby-risk publish-public --mode dry-run`)."""

    directory: Path = DRY_RUN_DIR

    def table(self, name: str) -> pl.DataFrame:
        path = self.directory / f"{name}.csv"
        if not path.exists():
            raise PublicDataUnavailableError(
                f"{path} introuvable : lancer `rugby-risk publish-public --mode dry-run`"
            )
        frame = pl.read_csv(path)
        return make_public(frame, table=name, aggregated=name not in NOT_AGGREGATED)


@dataclass(frozen=True)
class SupabaseRepository:
    """Lectures PostgREST anonymes (la RLS n'autorise que select pour anon)."""

    url: str
    anon_key: str

    def table(self, name: str) -> pl.DataFrame:
        try:
            response = httpx.get(
                f"{self.url.rstrip('/')}/rest/v1/{name}",
                headers={"apikey": self.anon_key, "Authorization": f"Bearer {self.anon_key}"},
                timeout=HTTP_TIMEOUT_S,
            )
        except httpx.HTTPError as exc:
            raise PublicDataUnavailableError(f"Supabase injoignable ({name})") from exc
        if response.status_code >= HTTP_ERROR_FROM:
            raise PublicDataUnavailableError(f"Table publique indisponible : {name}")
        frame = pl.DataFrame(response.json())
        return make_public(frame, table=name, aggregated=name not in NOT_AGGREGATED)


def get_repository(request: Request) -> Repository:
    """Dépendance FastAPI : le dépôt rattaché à l'application (surchargeable en test)."""
    repository: Repository = request.app.state.repository
    return repository


RepositoryDep = Annotated[Repository, Depends(get_repository)]
