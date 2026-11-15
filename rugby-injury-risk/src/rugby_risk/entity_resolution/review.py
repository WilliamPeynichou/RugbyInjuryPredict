"""Human review queue for uncertain entity links."""

from pathlib import Path

import polars as pl

from rugby_risk.reference import REFERENCE_DIR
from rugby_risk.settings import get_settings

REVIEW_PATH = Path("review/er_queue.csv")


def write_review_queue(queue: pl.DataFrame, path: Path | None = None) -> Path:
    target = path or get_settings().data_dir / REVIEW_PATH
    target.parent.mkdir(parents=True, exist_ok=True)
    queue.write_csv(target)
    return target


def read_review_queue(path: Path | None = None) -> pl.DataFrame:
    target = path or get_settings().data_dir / REVIEW_PATH
    if not target.exists():
        return pl.DataFrame(
            schema={"key_l": pl.String, "key_r": pl.String, "match_probability": pl.Float64}
        )
    return pl.read_csv(target, infer_schema=False).with_columns(
        pl.col("match_probability").cast(pl.Float64, strict=False)
    )


def decide(key: str, player_id: str, overrides_path: Path | None = None) -> Path:
    """Record a human decision: player_id (existing), NEW or REJECT; drops any old decision."""
    target = overrides_path or REFERENCE_DIR / "er_overrides.csv"
    source, _, source_player_id = key.partition(":")
    frame = pl.read_csv(target, infer_schema=False)
    frame = frame.filter(
        ~((frame["source"] == source) & (frame["source_player_id"] == source_player_id))
    )
    frame.extend(
        pl.DataFrame(
            {"source": [source], "source_player_id": [source_player_id], "player_id": [player_id]}
        )
    )
    frame.write_csv(target)
    return target
