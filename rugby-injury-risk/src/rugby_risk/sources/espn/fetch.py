"""ESPN hidden JSON API: scoreboard per league/year, then `summary?event=` per match.

Live-only: PoliteClient raises SourceNotAuthorizedError until `espn` is authorized.
F08: European cups (summaries) and calendar (scoreboard pages).
"""

import json

from rugby_risk.http import PoliteClient

BASE_URL = "https://site.api.espn.com/apis/site/v2/sports/rugby"
# shortcut: ids relevés dans des dépôts publics (Top 14 = 270559 confirmé par la doc de recherche),
# les autres sont à vérifier au premier appel autorisé.
LEAGUES = {
    "TOP14": "270559",
    "SIX_NATIONS": "180659",
    "RWC": "164205",
    "TESTS": "289234",
    "CHAMPIONS_CUP": "271937",
    "CHALLENGE_CUP": "272073",
}


def scoreboard_url(league_id: str) -> str:
    return f"{BASE_URL}/{league_id}/scoreboard"


def summary_url(league_id: str, event_id: str) -> str:
    return f"{BASE_URL}/{league_id}/summary?event={event_id}"


async def fetch_league_year(client: PoliteClient, league_id: str, year: int) -> list[str]:
    """List completed events of a league for a calendar year, then fetch each summary."""
    board = await client.get(scoreboard_url(league_id), params={"dates": str(year), "limit": "400"})
    events = [
        str(e["id"])
        for e in json.loads(board.content).get("events", [])
        if e.get("status", {}).get("type", {}).get("completed")
    ]
    for event_id in events:
        await client.get(summary_url(league_id, event_id))
    return events
