"""Public-boundary guard (F25, docs/07 §2): nothing nominative, nothing under k players.

Every table leaving the local (nominative) world goes through `make_public`: forbidden
column names raise, cells supported by fewer than `MIN_SUPPORT` distinct players are dropped.
"""

from typing import Final

import polars as pl

from rugby_risk.errors import PrivacyViolationError

MIN_SUPPORT: Final = 10
SUPPORT_COLUMN: Final = "n_players_support"
FORBIDDEN_PUBLIC_COLUMNS: Final = frozenset(
    {
        "player_key",
        "player_id",
        "source_player_id",
        "full_name",
        "first_name",
        "last_name",
        "player_name",
        "name",
        "birth_date",
        "date_of_birth",
        "age",
        "match_id",
        "team_id",
        "team_name",
        "club",
        "nationality",
        "height_cm",
        "weight_kg",
    }
)


def assert_public_safe(df: pl.DataFrame, *, table: str = "?") -> None:
    """Raise if a forbidden (identifying) column is present."""
    leaked = {c.lower() for c in df.columns} & FORBIDDEN_PUBLIC_COLUMNS
    if leaked:
        raise PrivacyViolationError(f"{table} : colonnes interdites {sorted(leaked)}")


def enforce_aggregation(df: pl.DataFrame, min_support: int = MIN_SUPPORT) -> pl.DataFrame:
    """Drop every row supported by fewer than `min_support` distinct players."""
    if SUPPORT_COLUMN not in df.columns:
        raise PrivacyViolationError(f"Colonne {SUPPORT_COLUMN} absente : agrégation invérifiable")
    if min_support < MIN_SUPPORT:
        raise PrivacyViolationError(f"min_support={min_support} < {MIN_SUPPORT} interdit")
    return df.filter(pl.col(SUPPORT_COLUMN) >= min_support)


def make_public(df: pl.DataFrame, *, table: str, aggregated: bool = True) -> pl.DataFrame:
    """Single entry point before any write. `aggregated=False` only for model metadata."""
    assert_public_safe(df, table=table)
    return enforce_aggregation(df) if aggregated else df
