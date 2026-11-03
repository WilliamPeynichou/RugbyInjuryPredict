"""International assets: staging from the raw lake (offline) + minutes consistency report."""

from pathlib import Path

import polars as pl
from dagster import AssetExecutionContext, Output, asset

from orchestration.assets.allrugby import _content
from orchestration.partitions import season_partitions
from rugby_risk.http import RawStore
from rugby_risk.parsers.espn import parse_summary
from rugby_risk.parsers.intl import IntlParseError
from rugby_risk.parsers.worldrugby import parse_match
from rugby_risk.settings import get_settings
from rugby_risk.warehouse import staging_frame, write_staging

FULL_TEAM_MINUTES = 15 * 80
MAX_GAP = 0.05


def _write(context: AssetExecutionContext, source: str, parsed: list, quarantined: list) -> Output:
    season_id = context.partition_key
    matches, appearances = [], []
    for match, rows in parsed:
        if match["season_id"] == season_id:  # le lac n'est pas partitionné par saison
            matches.append(match)
            appearances.extend(rows)
    for entry in quarantined:
        context.log.warning("Quarantaine %s: %s (%s)", source, entry["reason"], entry["url"])
    write_staging(staging_frame("match", matches), "match", source, season_id)
    write_staging(staging_frame("appearance", appearances), "appearance", source, season_id)
    return Output(None, metadata={"matches": len(matches), "quarantined": len(quarantined)})


@asset(partitions_def=season_partitions, compute_kind="python")
def intl_staging_worldrugby(context: AssetExecutionContext) -> Output:
    """Parse World Rugby summaries (+ timelines) from the raw lake into staging."""
    store = RawStore()
    parsed, quarantined = [], []
    for row in store.iter_manifest("worldrugby"):
        url = row.url_canonical
        if not url.endswith("/summary"):
            continue
        timeline = store.get_latest("worldrugby", url.removesuffix("/summary") + "/timeline")
        try:
            parsed.append(
                parse_match(
                    _content(store, url, "worldrugby"),
                    timeline.content.decode() if timeline else None,
                )
            )
        except IntlParseError as error:
            quarantined.append({"url": url, "reason": str(error)})
    return _write(context, "worldrugby", parsed, quarantined)


@asset(partitions_def=season_partitions, compute_kind="python")
def intl_staging_espn(context: AssetExecutionContext) -> Output:
    """Parse ESPN summaries from the raw lake into staging (lineups, no minutes)."""
    store = RawStore()
    parsed, quarantined = [], []
    for row in store.iter_manifest("espn"):
        if "/summary?" not in row.url_canonical:
            continue
        try:
            parsed.append(parse_summary(_content(store, row.url_canonical, "espn")))
        except IntlParseError as error:
            quarantined.append({"url": row.url_canonical, "reason": str(error)})
    return _write(context, "espn", parsed, quarantined)


def _team_totals(staging: Path, source: str, season_id: str) -> pl.DataFrame | None:
    def path(entity: str) -> Path:
        return staging / entity / f"source={source}" / f"season={season_id}" / "part.parquet"

    if not path("appearance").exists():
        return None
    matches, apps = pl.read_parquet(path("match")), pl.read_parquet(path("appearance"))
    return (
        apps.group_by(["source_match_id", "team_name"])
        .agg(pl.col("minutes_played").sum().alias("minutes"), pl.len().alias("players"))
        .join(
            matches.select(
                "source_match_id",
                pl.col("kickoff_ts").dt.date().alias("match_date"),
                "home_team_name",
                "away_team_name",
            ),
            on="source_match_id",
        )
        .drop("source_match_id")
    )


@asset(partitions_def=season_partitions, compute_kind="python")
def intl_minutes_check(context: AssetExecutionContext) -> Output:
    """Per match/team: World Rugby minutes vs 15x80 and matchday-squad size vs ESPN.

    ESPN has no minutes, so the cross-source check compares squad sizes; the minutes gap
    (> 5 %) is checked against the full-team reference instead.
    """
    season_id = context.partition_key
    staging = get_settings().data_dir / "staging"
    wr = _team_totals(staging, "worldrugby", season_id)
    if wr is None:
        return Output(None, metadata={"flagged": 0, "note": "worldrugby absent"})
    espn = _team_totals(staging, "espn", season_id)
    keys = ["match_date", "home_team_name", "away_team_name", "team_name"]
    if espn is not None:
        wr = wr.join(
            espn.select(*keys, pl.col("players").alias("espn_players")), on=keys, how="left"
        )
    else:
        wr = wr.with_columns(pl.lit(None, dtype=pl.UInt32).alias("espn_players"))
    report = wr.with_columns(
        ((pl.col("minutes") - FULL_TEAM_MINUTES).abs() / FULL_TEAM_MINUTES).alias("minutes_gap"),
        pl.lit(season_id).alias("season_id"),
    ).with_columns(
        (
            (pl.col("minutes_gap") > MAX_GAP)
            | (pl.col("espn_players").is_not_null() & (pl.col("espn_players") != pl.col("players")))
        ).alias("flagged")
    )
    out_dir = staging / "_reports" / "intl_minutes"
    out_dir.mkdir(parents=True, exist_ok=True)
    report.write_parquet(out_dir / f"season={season_id}.parquet", compression="zstd")
    return Output(None, metadata={"rows": report.height, "flagged": int(report["flagged"].sum())})
