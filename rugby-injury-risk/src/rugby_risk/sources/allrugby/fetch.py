"""Discovery of allrugby pages for a season; live runs require `authorized: true`."""

import re

from selectolax.lexbor import LexborHTMLParser

from rugby_risk.http import PoliteClient, RawStore
from rugby_risk.sources.allrugby.urls import match_page_url, player_page_url, season_page_url

MATCH_ID_PATTERN = re.compile(r"/matches/([a-z0-9-]+)", re.IGNORECASE)
PLAYER_ID_PATTERN = re.compile(r"/joueurs/[a-z0-9-]+-(\d+)\.html", re.IGNORECASE)


def _collect(html: str, pattern: re.Pattern[str]) -> list[str]:
    found = [
        m.group(1)
        for a in LexborHTMLParser(html).css("a")
        if (m := pattern.search(a.attributes.get("href") or ""))
    ]
    return sorted(set(found))


async def fetch_season(
    client: PoliteClient,
    season_id: str,
    *,
    known_player_ids: set[str] | None = None,
    store: RawStore | None = None,
) -> dict[str, list[str]]:
    """Fetch the season page, every match page, then each player page once.

    Returns {"match_ids": [...], "player_ids": [...]}. Live-only: the PoliteClient
    guard raises SourceNotAuthorizedError until `allrugby` is authorized by a human.
    """
    store = store or client.store
    season = await client.get(season_page_url(season_id))
    match_ids = _collect(season.content.decode(), MATCH_ID_PATTERN)
    player_ids = set(known_player_ids or set())
    for match_id in match_ids:
        match = await client.get(match_page_url(match_id))
        player_ids.update(_collect(match.content.decode(), PLAYER_ID_PATTERN))
    fetched_ids = {
        m.group(1)
        for row in store.iter_manifest("allrugby")
        if (m := PLAYER_ID_PATTERN.search(row.url_canonical))
    }
    fresh = []
    for player_id in sorted(player_ids):
        if player_id not in fetched_ids:
            fresh.append(player_id)
            await client.get(player_page_url(player_id))
    return {"match_ids": match_ids, "player_ids": fresh}
