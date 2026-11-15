"""Unified fixture calendar asset (all staged sources + ESPN scoreboard pages)."""

import polars as pl
from dagster import AssetExecutionContext, Output, asset

from orchestration.assets.allrugby import _content
from orchestration.partitions import season_partitions
from rugby_risk.calendar import build_calendar
from rugby_risk.http import RawStore
from rugby_risk.parsers.espn import parse_scoreboard
from rugby_risk.settings import get_settings
from rugby_risk.warehouse import staging_frame, write_staging


@asset(partitions_def=season_partitions, compute_kind="python")
def calendar_staging(context: AssetExecutionContext) -> Output:
    """Merge staged matches of every source + ESPN scoreboards; report kickoff conflicts."""
    season_id = context.partition_key
    staging = get_settings().data_dir / "staging"
    frames = [
        pl.read_parquet(path).select(staging_frame("match", []).columns)
        for path in sorted((staging / "match").glob(f"source=*/season={season_id}/part.parquet"))
    ]
    store = RawStore()
    board = [
        row
        for entry in store.iter_manifest("espn")
        if "/scoreboard" in entry.url_canonical
        for row in parse_scoreboard(_content(store, entry.url_canonical, "espn"))
        if row["season_id"] == season_id
    ]
    frames.append(staging_frame("match", board))
    calendar, conflicts, unresolved = build_calendar(pl.concat(frames, how="vertical_relaxed"))
    for name in sorted(unresolved):
        context.log.warning("Équipe sans alias: %s", name)
    write_staging(calendar, "fixture_calendar", "all", season_id)
    out_dir = staging / "_reports" / "calendar_conflicts"
    out_dir.mkdir(parents=True, exist_ok=True)
    conflicts.write_parquet(out_dir / f"season={season_id}.parquet", compression="zstd")
    return Output(
        None,
        metadata={
            "matches": calendar.height,
            "conflicts": conflicts.height,
            "unresolved_teams": len(unresolved),
        },
    )
