"""Post-resolution invariants (checked by Dagster asset checks)."""

import polars as pl

UNIQUE_KEY = "unique_source_id"
NO_DOUBLE_SHEET = "no_double_sheet_same_day"
STABLE_IDS = "stable_player_ids"


def check_unique_source_id(xref: pl.DataFrame) -> pl.DataFrame:
    """A (source, source_player_id) pair has exactly one player_id (xref PK enforces it)."""
    if xref.is_empty():
        return pl.DataFrame(schema={"key": pl.String, "player_id": pl.Int64})
    dupes = (
        xref.group_by(["source", "source_player_id"])
        .agg(pl.len().alias("n"), pl.col("player_id").n_unique().alias("ids"))
        .filter((pl.col("n") > 1) | (pl.col("ids") > 1))
    )
    return xref.join(dupes.select("source", "source_player_id"), on=["source", "source_player_id"])


def check_no_double_sheet_same_day(
    xref: pl.DataFrame, apps: pl.DataFrame, previous: pl.DataFrame | None
) -> pl.DataFrame:
    """No player_id on two different matches the same day."""
    combined = (
        xref
        if previous is None or previous.is_empty()
        else xref.join(
            previous.select("key", pl.col("player_id").alias("previous_player_id")),
            on="key",
            how="left",
        )
        .with_columns(pl.coalesce(["player_id", "previous_player_id"]).alias("player_id"))
        .select(xref.columns)
    )
    violations = (
        apps.join(combined.select("key", "player_id"), on="key")
        .group_by(["player_id", "match_date"])
        .agg(pl.col("match_key").n_unique().alias("matches"))
        .filter(pl.col("matches") > 1)
    )
    return violations


def check_stable_ids(xref: pl.DataFrame, previous: pl.DataFrame | None) -> pl.DataFrame:
    """A key keeps its previous player_id (records that disappear are ignored)."""
    if previous is None or previous.is_empty():
        return pl.DataFrame(schema={"key": pl.String, "old": pl.Int64, "new": pl.Int64})
    moved = (
        previous.join(
            xref.select("key", pl.col("player_id").alias("new_id")), on="key", how="inner"
        )
        .filter(pl.col("player_id") != pl.col("new_id"))
        .select(pl.col("key"), pl.col("player_id").alias("old"), pl.col("new_id").alias("new"))
    )
    return moved
