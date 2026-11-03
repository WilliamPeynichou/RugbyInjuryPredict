"""Découverte des feuilles de match LNR ; live-only (garde-fou F03 actif)."""

import re

from selectolax.lexbor import LexborHTMLParser

from rugby_risk.http import PoliteClient
from rugby_risk.sources.lnr.urls import BASE_URL, calendar_url

LINEUP_PATTERN = re.compile(
    r"/feuille-de-match/([a-z0-9-]+/[a-z0-9]+/\d+-[a-z0-9-]+)/compositions", re.IGNORECASE
)


def lineup_url_from_tail(tail: str) -> str:
    return f"{BASE_URL}/feuille-de-match/{tail}/compositions"


async def fetch_season_rounds(client: PoliteClient, season_id: str) -> list[str]:
    """Liste les feuilles de match (suffixes d'URL) d'une saison, puis les récupère."""
    calendar = await client.get(calendar_url(season_id))
    found = []
    for anchor in LexborHTMLParser(calendar.content.decode()).css("a"):
        href = anchor.attributes.get("href")
        if href and (match := LINEUP_PATTERN.search(href)):
            found.append(match.group(1))
    tails = sorted(set(found))
    for tail in tails:
        await client.get(lineup_url_from_tail(tail))
    return tails
