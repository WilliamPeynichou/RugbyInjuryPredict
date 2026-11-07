"""F16 asset helpers: read warehouse signal frames and build fusion Signals."""

from datetime import date
from typing import cast

import polars as pl

from rugby_risk.injuries.fusion import ONSET_ABSENCE, ONSET_ANNOUNCEMENT, ONSET_EXIT, Signal


def exit_signals(exit_frame: pl.DataFrame) -> list[Signal]:
    signals = []
    for row in exit_frame.iter_rows(named=True):
        signals.append(
            Signal(
                kind=ONSET_EXIT,
                player_id=int(row["player_id"]),
                signal_date=row["match_date"],
                strength=float(row["signal_strength"]),
                match_id=int(row["match_id"]),
                context="match",
                evidence=[
                    {
                        "kind": "exit",
                        "match_id": row["match_id"],
                        "minute_off": row["minute_off"],
                        "off_reason_derived": row["off_reason_derived"],
                        "signal_strength": row["signal_strength"],
                    }
                ],
            )
        )
    return signals


def absence_signals(runs: pl.DataFrame, returns: dict[tuple[int, date], date]) -> list[Signal]:
    signals = []
    for row in runs.iter_rows(named=True):
        key = (int(row["player_id"]), row["start_date"])
        signals.append(
            Signal(
                kind=ONSET_ABSENCE,
                player_id=int(row["player_id"]),
                signal_date=row["start_date"],
                strength=1.0,
                match_id=row["prev_played_match_id"],
                run_end=row["end_date"],
                return_date=returns.get(key),
                censored_end=bool(row["censored_end_of_season"]),
                evidence=[
                    {
                        "kind": "absence",
                        "start_date": str(row["start_date"]),
                        "end_date": str(row["end_date"]),
                        "n_matches": row["n_matches"],
                        "prev_played_match_id": row["prev_played_match_id"],
                    }
                ],
            )
        )
    return signals


def announcement_signals(mentions: pl.DataFrame) -> list[Signal]:
    signals = []
    for row in mentions.iter_rows(named=True):
        detailed = bool(row["body_region"]) or row["announced_duration_days_min"] is not None
        signals.append(
            Signal(
                kind=ONSET_ANNOUNCEMENT,
                player_id=int(row["player_id"]),
                signal_date=row["onset_date"],
                strength=1.0,
                match_id=row["match_id"],
                context=str(row["onset_context"]),
                body_region=row["body_region"],
                injury_type=row["injury_type"],
                is_concussion=bool(row["is_concussion"]),
                detailed=detailed,
                evidence=[
                    {
                        "kind": "announcement",
                        "mention_id": row["mention_id"],
                        "doc_url": row.get("doc_url"),
                        "published_at": str(row["published_at"]),
                        "quote": (row["quote"] or "")[:200],
                    }
                ],
            )
        )
    return signals


def first_returns_after(
    eligibility: pl.DataFrame, runs: pl.DataFrame
) -> dict[tuple[int, date], date]:
    """First played (on_sheet) match date after each absence run, per player."""
    played = eligibility.filter(pl.col("on_sheet")).select(
        ["player_id", "match_date", "kickoff_ts"]
    )
    out: dict[tuple[int, date], date] = {}
    for row in runs.iter_rows(named=True):
        pid, start, end = int(row["player_id"]), row["start_date"], row["end_date"]
        after = played.filter(
            (pl.col("player_id") == pid)
            & (pl.col("match_date") > end)
            & (pl.col("match_date") <= date(end.year + 1, 6, 30))
        )
        if after.height:
            first = cast(date, after.sort("kickoff_ts")["match_date"][0])
            out[(pid, start)] = first
    return out
