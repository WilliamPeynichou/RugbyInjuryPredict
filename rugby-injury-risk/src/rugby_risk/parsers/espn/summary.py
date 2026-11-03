"""Parse an ESPN rugby `summary?event=` payload into staging rows.

PARSER_VERSION = espn-1
Payload shape (see src/rugby_risk/sources/espn/README.md): `header.id`,
`header.league.name`, `header.competitions[0]` (date ISO UTC, competitors[] with
homeAway / team.displayName / score), `gameInfo.venue.fullName`, and
`rosters[]` (homeAway, team.displayName, roster[] with jersey / athlete.id /
athlete.displayName). ESPN gives no on/off times: minutes are NULL. Its
`starter` flag is unreliable (transientlunatic/Rugby-Data): starter = jersey 1-15.
"""

import json
from datetime import datetime
from typing import Any

from rugby_risk.config.seasons import season_for_date
from rugby_risk.parsers.intl import IntlParseError, competition_code
from rugby_risk.reference import position_from_shirt
from rugby_risk.staging_schemas import StagingAppearance, StagingMatch
from rugby_risk.warehouse import staging_frame

PARSER_VERSION = "espn-1"
SOURCE = "espn"
STARTERS = 15


def _score(competitor: dict[str, Any]) -> int | None:
    value = str(competitor.get("score", ""))
    return int(value) if value.isdigit() else None


def parse_summary(payload: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    data = json.loads(payload)
    header = data.get("header") or {}
    event_id = str(header.get("id") or "")
    if not event_id:
        raise IntlParseError("header.id absent")
    competitions = header.get("competitions") or [{}]
    sides = {c.get("homeAway"): c for c in competitions[0].get("competitors", [])}
    if set(sides) != {"home", "away"}:
        raise IntlParseError("Adversaires incomplets")
    kickoff_ts = datetime.fromisoformat(competitions[0]["date"].replace("Z", "+00:00"))
    season_id = season_for_date(kickoff_ts.date())
    if season_id is None:
        raise IntlParseError(f"Date hors saisons: {kickoff_ts.date()}")
    rosters = {r.get("homeAway"): r for r in data.get("rosters") or []}
    if set(rosters) != {"home", "away"}:
        raise IntlParseError("Compositions absentes")
    appearances: list[dict[str, object]] = []
    for side in ("home", "away"):
        team = sides[side]["team"]["displayName"]
        players = [p for p in rosters[side].get("roster", []) if str(p.get("jersey", "")).isdigit()]
        if len([p for p in players if int(p["jersey"]) <= STARTERS]) != STARTERS:
            raise IntlParseError(f"{team}: composition sans 15 titulaires")
        for p in players:
            shirt = int(p["jersey"])
            appearances.append(
                {
                    "source": SOURCE,
                    "source_match_id": event_id,
                    "source_player_id": str(p["athlete"]["id"]),
                    "player_name": p["athlete"]["displayName"],
                    "team_name": team,
                    "shirt_number": shirt,
                    "is_starter": shirt <= STARTERS,
                    "position_raw": position_from_shirt(shirt) or "unknown",
                    "minutes_played": None,
                    # shortcut: cartons non lus (stats ESPN non documentées), à brancher en F12.
                    "yellow_cards": 0,
                    "red_cards": 0,
                }
            )
    match: dict[str, object] = {
        "source": SOURCE,
        "source_match_id": event_id,
        "competition_code": competition_code(
            str((header.get("league") or {}).get("name") or ""), kickoff_ts.date()
        ),
        "season_id": season_id,
        "round": None,
        "kickoff_ts": kickoff_ts,
        "kickoff_time_imputed": False,
        "venue_name": ((data.get("gameInfo") or {}).get("venue") or {}).get("fullName"),
        "home_team_name": sides["home"]["team"]["displayName"],
        "away_team_name": sides["away"]["team"]["displayName"],
        "home_score": _score(sides["home"]),
        "away_score": _score(sides["away"]),
    }
    StagingMatch.validate(staging_frame("match", [match]))
    StagingAppearance.validate(staging_frame("appearance", appearances))
    return match, appearances
