"""World Rugby pulselive API: match list per period, then summary + timeline per match.

Live-only: PoliteClient raises SourceNotAuthorizedError until `worldrugby` is authorized.
"""

import json
from datetime import date
from typing import Any

from rugby_risk.http import PoliteClient

BASE_URL = "https://api.wr-rims-prod.pulselive.com/rugby/v3"
PAGE_SIZE = 100
COMPLETE = "C"
# Nations couvertes (fiche F07) : joueurs présents en Top 14.
TRACKED_NATIONS = frozenset(
    {
        "France",
        "England",
        "Ireland",
        "Scotland",
        "Wales",
        "Italy",
        "South Africa",
        "New Zealand",
        "Australia",
        "Argentina",
        "Fiji",
        "Samoa",
        "Tonga",
        "Georgia",
        "Japan",
    }
)


def match_list_url() -> str:
    return f"{BASE_URL}/match"


def summary_url(match_alt_id: str) -> str:
    return f"{BASE_URL}/match/{match_alt_id}/summary"


def timeline_url(match_alt_id: str) -> str:
    return f"{BASE_URL}/match/{match_alt_id}/timeline"


def tracked(match: dict[str, Any]) -> bool:
    names = {t.get("name") for t in match.get("teams", [])}
    return match.get("status") == COMPLETE and bool(names & TRACKED_NATIONS)


async def fetch_period(client: PoliteClient, start: date, end: date) -> list[str]:
    """Page through men's XV matches in [start, end]; fetch details of tracked ones."""
    alt_ids: list[str] = []
    page, pages = 0, 1
    while page < pages:
        params = {
            "sport": "mru",
            "states": COMPLETE,
            "sort": "asc",
            "page": str(page),
            "pageSize": str(PAGE_SIZE),
            "startDate": start.isoformat(),
            "endDate": end.isoformat(),
        }
        body = json.loads((await client.get(match_list_url(), params=params)).content)
        pages = int(body["pageInfo"]["numPages"])
        alt_ids.extend(str(m["matchAltId"]) for m in body["content"] if tracked(m))
        page += 1
    for alt_id in alt_ids:
        await client.get(summary_url(alt_id))
        await client.get(timeline_url(alt_id))
    return alt_ids
