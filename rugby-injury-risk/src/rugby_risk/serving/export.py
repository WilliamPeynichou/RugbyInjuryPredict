"""Publication of the aggregated tables (F25): dry-run (files) or Supabase (upsert).

`publish` is the single write path. Every table passes `make_public` inside
`build_public_tables` AND once more here: a sink never writes anything that was not
re-checked. Supabase writes are refused unless the artifact carries a human-written
`PROMOTION.md` (docs/06 §5): an unpromoted model only ever publishes to the dry-run folder.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Final, Protocol

import httpx
import polars as pl

from rugby_risk.errors import PrivacyViolationError
from rugby_risk.serving.batch import TABLES, PublicTables
from rugby_risk.serving.guard import make_public

DRY_RUN_DIR: Final = Path("reports/public_preview")
_HTTP_ERROR: Final = 400
# Clé de conflit = clé primaire de chaque table (supabase/migrations/0001_public_tables.sql).
CONFLICT_KEYS: Final[dict[str, tuple[str, ...]]] = {
    "pred_position_curve": (
        "model_version",
        "season_id",
        "position_code",
        "scenario",
        "n_consecutive",
    ),
    "pred_position_season": ("model_version", "season_id", "position_code"),
    "calibration_public": ("model_version", "test_season", "position_group", "bin"),
    "model_registry_public": ("model_version",),
}


class PublishTransportError(RuntimeError):
    """Écriture distante refusée (HTTP ≥ 400) : ce n'est pas une violation de confidentialité."""


class Sink(Protocol):
    """One write target for one table."""

    def write(self, table: str, df: pl.DataFrame) -> None: ...


@dataclass(frozen=True)
class DryRunSink:
    """Deterministic file sink: same inputs -> same files (upsert idempotent, no clobber)."""

    directory: Path = DRY_RUN_DIR

    def write(self, table: str, df: pl.DataFrame) -> None:
        self.directory.mkdir(parents=True, exist_ok=True)
        path = self.directory / f"{table}.csv"
        if path.exists() and path.read_text(encoding="utf-8") == df.write_csv():
            return  # idempotent : rien à changer
        df.write_csv(path)


@dataclass(frozen=True)
class SupabaseSink:
    """PostgREST upsert through httpx (already a dependency); the service key never ships."""

    url: str
    service_key: str

    def write(self, table: str, df: pl.DataFrame) -> None:
        response = httpx.post(
            f"{self.url.rstrip('/')}/rest/v1/{table}",
            params={"on_conflict": ",".join(CONFLICT_KEYS[table])},
            headers={
                "apikey": self.service_key,
                "Authorization": f"Bearer {self.service_key}",
                "Prefer": "resolution=merge-duplicates",
            },
            content=df.write_json(),
        )
        if response.status_code >= _HTTP_ERROR:
            raise PublishTransportError(
                f"Écriture Supabase refusée ({table}, HTTP {response.status_code})"
            )


def publish(public: PublicTables, sink: Sink) -> None:
    """Write every table through a final guard pass. Nothing reaches a sink unchecked."""
    missing = [t for t in TABLES if t not in public.tables]
    if missing:
        raise PrivacyViolationError(f"Tables publiques manquantes : {missing}")
    aggregated = {
        "model_registry_public": False,
    }
    for table in TABLES:
        frame = public.tables[table]
        sink.write(table, make_public(frame, table=table, aggregated=aggregated.get(table, True)))
