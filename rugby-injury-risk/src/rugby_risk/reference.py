"""Validated local reference CSVs; cached frames are never exposed directly."""

from datetime import date
from functools import lru_cache
from pathlib import Path

import pandera.polars as pa
import polars as pl

from rugby_risk.config.seasons import load_seasons

REFERENCE_DIR = Path("data/reference")


def _intervals(frame: pl.DataFrame, group: str | None = None) -> bool:
    if frame.filter(pl.col("start_date") > pl.col("end_date")).height:
        return False
    groups = frame.partition_by(group) if group else [frame]
    for rows in groups:
        ends = rows.sort("start_date").get_column("end_date").to_list()
        starts = rows.sort("start_date").get_column("start_date").to_list()
        if any(end >= start for end, start in zip(ends, starts[1:], strict=False)):
            return False
    return True


def _schema(name: str) -> pa.DataFrameSchema:
    def text() -> pa.Column:
        return pa.Column(pl.String, checks=pa.Check.str_length(min_value=1))

    schemas = {
        "positions": {
            "position_code": pa.Column(pl.String, unique=True),
            "position_label_fr": text(),
            "position_group": text(),
            "unit": text(),
            "shirt_numbers": text(),
        },
        "competitions": {
            "competition_code": pa.Column(pl.String, unique=True),
            "name": text(),
            "level": pa.Column(
                pl.String, pa.Check.isin(["club_domestic", "club_europe", "international"])
            ),
        },
        "venues": {
            "venue_id": pa.Column(pl.Int64, unique=True),
            "name": text(),
            "city": text(),
            "country": text(),
            "lat": pa.Column(pl.Float64, nullable=True, checks=pa.Check.in_range(-90, 90)),
            "lon": pa.Column(pl.Float64, nullable=True, checks=pa.Check.in_range(-180, 180)),
        },
        "venue_surface": {
            "venue_id": pa.Column(pl.Int64),
            "season_id": text(),
            "surface": pa.Column(
                pl.String, pa.Check.isin(["natural", "hybrid", "synthetic", "unknown"])
            ),
            "source": text(),
        },
        "test_windows": {
            "window_id": pa.Column(pl.String, unique=True),
            "label": text(),
            "start_date": pa.Column(pl.Date),
            "end_date": pa.Column(pl.Date),
            "type": pa.Column(pl.String, pa.Check.isin(["six_nations", "autumn", "summer", "rwc"])),
        },
        "rules_protection": {
            "regime": pa.Column(pl.String, unique=True),
            "start_date": pa.Column(pl.Date),
            "end_date": pa.Column(pl.Date),
            "list_size": pa.Column(pl.Int64, nullable=True),
            **{
                column: pa.Column(pl.Int64, nullable=True)
                for column in ("max_matches", "min_minutes", "offseason_weeks", "max_tests")
            },
            "rest_rule": pa.Column(pl.String, nullable=True),
            "source": text(),
        },
        "protected_players": {"season_id": text(), "player_name": text(), "source_url": text()},
        "opt_out": {"player_id": pa.Column(pl.Int64, unique=True)},
        "er_overrides": {"source": text(), "source_player_id": text(), "player_id": text()},
    }
    return pa.DataFrameSchema(schemas[name], strict=True, coerce=True)


@lru_cache
def _load(name: str) -> pl.DataFrame:
    schema = _schema(name)
    frame = pl.read_csv(REFERENCE_DIR / f"{name}.csv", infer_schema=False, null_values="NULL")
    if name in {"test_windows", "rules_protection"}:
        frame = frame.with_columns(
            pl.col("start_date", "end_date").str.to_date("%Y-%m-%d", strict=True)
        )
    frame = schema.validate(frame)
    if name in {"test_windows", "rules_protection"} and not _intervals(
        frame, "type" if name == "test_windows" else None
    ):
        raise ValueError(f"Invalid or overlapping intervals in {name}")
    if name == "positions":
        if (frame.height, frame["position_group"].n_unique(), frame["unit"].n_unique()) != (
            9,
            6,
            2,
        ):
            raise ValueError("Expected 9 positions, 6 groups and 2 units")
        shirts = [
            int(number)
            for numbers in frame["shirt_numbers"]
            for number in numbers.split(";")
            if int(number) in range(1, 16)
        ]
        if sorted(shirts) != list(range(1, 16)):
            raise ValueError("Starting shirt numbers must cover 1..15 exactly once")
    if name == "venue_surface":
        if frame.select("venue_id", "season_id").is_duplicated().any():
            raise ValueError("Duplicate venue-season surface")
        if not set(frame["venue_id"]).issubset(venues()["venue_id"]):
            raise ValueError("Unknown venue in surfaces")
        if not set(frame["season_id"]).issubset(s.season_id for s in load_seasons()):
            raise ValueError("Unknown season in surfaces")
    return frame


def positions() -> pl.DataFrame:
    return _load("positions").clone()


def competitions() -> pl.DataFrame:
    return _load("competitions").clone()


def venues() -> pl.DataFrame:
    return _load("venues").clone()


def venue_surface() -> pl.DataFrame:
    return _load("venue_surface").clone()


def test_windows() -> pl.DataFrame:
    return _load("test_windows").clone()


def rules_protection() -> pl.DataFrame:
    return _load("rules_protection").clone()


def protected_players() -> pl.DataFrame:
    return _load("protected_players").clone()


def opt_out() -> pl.DataFrame:
    return _load("opt_out").clone()


def er_overrides() -> pl.DataFrame:
    return _load("er_overrides").clone()


def position_group(code: str) -> str:
    rows = positions().filter(pl.col("position_code") == code)
    if rows.is_empty():
        raise ValueError(f"Unknown position: {code}")
    return str(rows.item(0, "position_group"))


def position_from_shirt(n: int) -> str | None:
    if n not in range(1, 16):
        return None
    for row in positions().iter_rows(named=True):
        if str(n) in str(row["shirt_numbers"]).split(";"):
            return str(row["position_code"])
    return None


def in_test_window(d: date) -> bool:
    return (
        not test_windows()
        .filter((pl.col("start_date") <= d) & (pl.col("end_date") >= d))
        .is_empty()
    )


def protection_regime(d: date) -> str:
    rows = rules_protection().filter((pl.col("start_date") <= d) & (pl.col("end_date") >= d))
    return "unknown" if rows.is_empty() else str(rows.item(0, "regime"))
