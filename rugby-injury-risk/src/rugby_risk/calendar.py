"""Unified fixture calendar: merge staged matches of every source, one row per match.

kickoff_ts priority: LNR > allrugby > World Rugby > ESPN > API-Sports; an imputed kickoff
time (allrugby 15:00) always loses to an observed one. Observed kickoffs more than 2 hours
apart for the same match are reported as conflicts.
"""

from datetime import timedelta

import polars as pl

from rugby_risk.reference import team_canonical, venue_id
from rugby_risk.warehouse import staging_frame

PRIORITY = {"lnr": 0, "allrugby": 1, "worldrugby": 2, "espn": 3, "apisports": 4}
KEY = ["competition_code", "season_id", "home_team_name", "away_team_name", "match_date"]
MAX_GAP = timedelta(hours=2)


def build_calendar(matches: pl.DataFrame) -> tuple[pl.DataFrame, pl.DataFrame, set[str]]:
    """Return (calendar, conflicts, unresolved team names) from staging `match` rows."""
    rows, unresolved = [], set()
    for row in matches.to_dicts():
        for side in ("home_team_name", "away_team_name"):
            canonical = team_canonical(row[side], row["source"])
            if canonical is None:
                unresolved.add(row[side])
            row[side] = canonical or row[side]
        row["venue_id"] = venue_id(row["venue_name"])
        row["priority"] = PRIORITY.get(row["source"], len(PRIORITY))
        rows.append(row)
    frame = (
        pl.DataFrame(rows, schema_overrides={"venue_id": pl.Int64, "priority": pl.Int64})
        if rows
        else staging_frame("fixture_calendar", []).with_columns(pl.lit(0).alias("priority"))
    )
    frame = frame.with_columns(pl.col("kickoff_ts").dt.date().alias("match_date")).sort(
        "kickoff_time_imputed", "priority"
    )
    columns = staging_frame("fixture_calendar", []).columns
    rest = [c for c in columns if c not in KEY]
    calendar = (
        frame.group_by(KEY, maintain_order=True)
        .agg(pl.col(c).drop_nulls().first() for c in rest)
        .select(columns)
        .sort("kickoff_ts")
    )
    conflicts = (
        frame.filter(~pl.col("kickoff_time_imputed"))
        .group_by(KEY)
        .agg(
            pl.col("kickoff_ts").min().alias("kickoff_min"),
            pl.col("kickoff_ts").max().alias("kickoff_max"),
            pl.col("source").unique().sort().str.join(",").alias("sources"),
        )
        .filter(pl.col("kickoff_max") - pl.col("kickoff_min") > MAX_GAP)
        .sort(KEY)
    )
    return staging_frame("fixture_calendar", calendar.to_dicts()), conflicts, unresolved
