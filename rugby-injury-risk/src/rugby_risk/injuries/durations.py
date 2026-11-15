"""Convert French announced durations to day ranges (F15).

The LLM returns the raw wording (`announced_duration_text`); this module turns it into
`announced_duration_days_min/max`. Unknown or open-ended wordings give (None, None).
"""

import re

# shortcut: patterns cover the formulations seen in French rugby press; extend on real data.
_WEEKS = re.compile(r"(\d+)\s*(?:à|--|-|et)\s*(\d+)\s*semaines?")
_WEEK = re.compile(r"(\d+)\s*semaines?")
_DAYS = re.compile(r"(\d+)\s*(?:à|--|-|et)\s*(\d+)\s*jours?")
_DAY = re.compile(r"(\d+)\s*jours?")
_MONTHS = re.compile(r"(\d+)\s*mois")


def parse_duration(  # noqa: PLR0911 - one return per pattern
    text: str | None,
) -> tuple[int | None, int | None]:
    """('4 à 6 semaines') -> (28, 42). 'fin de saison' and vague wording -> (None, None)."""
    if not text:
        return None, None
    cleaned = text.strip().lower()
    if "saison" in cleaned:
        return None, None
    if match := _WEEKS.search(cleaned):
        return int(match.group(1)) * 7, int(match.group(2)) * 7
    if match := _MONTHS.search(cleaned):
        months = int(match.group(1))
        return months * 28, months * 31
    if match := _DAYS.search(cleaned):
        return int(match.group(1)), int(match.group(2))
    if match := _WEEK.search(cleaned):
        return int(match.group(1)) * 7, int(match.group(1)) * 7
    if match := _DAY.search(cleaned):
        return int(match.group(1)), int(match.group(1))
    return None, None
