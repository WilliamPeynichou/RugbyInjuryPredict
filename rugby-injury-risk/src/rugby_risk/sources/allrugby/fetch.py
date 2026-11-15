"""Discovery of allrugby pages for a season; live runs require `authorized: true`."""

import re

import httpx
import structlog
from selectolax.lexbor import LexborHTMLParser

from rugby_risk.http import FetchResult, PoliteClient
from rugby_risk.http.urls import canonicalize_url
from rugby_risk.sources.allrugby.urls import BASE_URL, season_page_url

PLAYER_PATH_PATTERN = re.compile(r"^/joueurs/[a-z0-9-]+-(\d+)\.html$", re.IGNORECASE)
log = structlog.get_logger()


def match_path_pattern(season_id: str) -> re.Pattern[str]:
    return re.compile(rf"^/saison-{season_id}/matchs/[a-z0-9-]+-(\d+)\.html$", re.IGNORECASE)


def collect_paths(html: str, pattern: re.Pattern[str]) -> list[str]:
    hrefs = (a.attributes.get("href") or "" for a in LexborHTMLParser(html).css("a"))
    return sorted({h for h in hrefs if pattern.match(h)})


async def _get_once(client: PoliteClient, path: str) -> FetchResult | None:
    """Lake copy if present (past pages do not change: resumable crawl), else polite GET."""
    url = canonicalize_url(BASE_URL + path)
    cached = client.store.get_latest("allrugby", url)
    if cached is not None:
        return cached
    try:
        return await client.get(url)
    except httpx.HTTPStatusError as error:  # one missing page must not stop the season
        log.warning("allrugby_page_skipped", url=url, status=error.response.status_code)
        return None


async def fetch_season(client: PoliteClient, season_id: str) -> dict[str, int]:
    """Fetch the Top 14 calendar, every match page, then every player page once."""
    season = await client.get(season_page_url(season_id))
    match_paths = collect_paths(season.content.decode(), match_path_pattern(season_id))
    player_paths: set[str] = set()
    for path in match_paths:
        page = await _get_once(client, path)
        if page is not None:
            player_paths.update(collect_paths(page.content.decode(), PLAYER_PATH_PATTERN))
    for path in sorted(player_paths):
        await _get_once(client, path)
    return {"match_pages": len(match_paths), "player_pages": len(player_paths)}
