"""Shared helpers for international match parsers (World Rugby, ESPN)."""

from datetime import date
from pathlib import Path

import polars as pl

ALIASES_PATH = Path("data/reference/competition_aliases.csv")
# Hors périmètre F07 : féminin, rugby à 7, jeunes. Testé avant les alias ("Women's Six Nations").
EXCLUDED_MARKERS = ("women", "sevens", "u20", "u18", "u19", "junior")


class IntlParseError(Exception):
    """An international match payload is invalid or out of scope; carries the reason."""


def load_competition_aliases(path: Path = ALIASES_PATH) -> list[tuple[str, str]]:
    frame = pl.read_csv(path)
    return list(zip(frame["pattern"].to_list(), frame["competition_code"].to_list(), strict=True))


def competition_code(label: str, kickoff: date) -> str:
    """Map a source event label to competitions.csv; generic tests fall back on the month."""
    lowered = label.lower()
    if any(marker in lowered for marker in EXCLUDED_MARKERS):
        raise IntlParseError(f"Hors périmètre: {label!r}")
    for pattern, code in load_competition_aliases():
        if pattern.lower() in lowered:
            return code
    if kickoff.month in (10, 11, 12):
        return "AUTUMN_TESTS"
    if kickoff.month in (6, 7, 8):
        return "SUMMER_TESTS"
    return "OTHER_TEST"
