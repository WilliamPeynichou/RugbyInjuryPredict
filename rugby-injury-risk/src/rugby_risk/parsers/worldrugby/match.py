"""Parse a World Rugby (pulselive) match summary + timeline into staging rows.

PARSER_VERSION = worldrugby-1
Payload shapes (see src/rugby_risk/sources/worldrugby/README.md):
- summary: `match` (matchId, competition, time.millis, venue, teams[].name, scores[])
  and `teams[i].teamList.list[]` (number, player.id, player.name.display);
- timeline: `timeline[]` (type, teamIndex, playerId, time.secs).
Minutes: "Sub On"/"Sub Off" are explicit; "IR"/"HIAO" tag both players at the same
second, so they toggle the player's state (method of bpcsaund/rugby-analytics).
"Red Card" takes the player off for good. No timeline -> minutes NULL.
"""

import json
from datetime import UTC, datetime
from typing import Any

from rugby_risk.config.seasons import season_for_date
from rugby_risk.parsers.intl import IntlParseError, competition_code
from rugby_risk.reference import position_from_shirt
from rugby_risk.staging_schemas import StagingAppearance, StagingMatch
from rugby_risk.warehouse import staging_frame

PARSER_VERSION = "worldrugby-1"
SOURCE = "worldrugby"
FULL_MATCH_SECS = 80 * 60
MAX_MINUTES = 100  # borne du schéma staging (prolongations comprises)
TOGGLE_TYPES = {"IR", "HIAO"}
MOVE_TYPES = {"Sub On", "Sub Off", "Red Card", *TOGGLE_TYPES}


def _minutes(starter: bool, events: list[tuple[int, str]], match_end: int) -> int:
    on, since, total = starter, 0, 0
    for secs, kind in sorted(e for e in events if e[1] in MOVE_TYPES):
        goes_off = kind in {"Sub Off", "Red Card"} or (kind in TOGGLE_TYPES and on)
        if goes_off and on:
            total += max(0, secs - since)
            on = False
        elif not goes_off and not on:  # un "on" redondant est ignoré
            on, since = True, secs
        if kind == "Red Card":
            break
    if on:
        total += max(0, match_end - since)
    return min(round(total / 60), MAX_MINUTES)


def _events(timeline: dict[str, Any] | None, team_idx: int) -> dict[str, list[tuple[int, str]]]:
    out: dict[str, list[tuple[int, str]]] = {}
    for event in (timeline or {}).get("timeline", []):
        if event.get("teamIndex") == team_idx and event.get("playerId"):
            out.setdefault(str(event["playerId"]), []).append(
                (int(event["time"]["secs"]), str(event["type"]))
            )
    return out


def parse_match(
    summary_json: str, timeline_json: str | None = None
) -> tuple[dict[str, object], list[dict[str, object]]]:
    summary = json.loads(summary_json)
    timeline = json.loads(timeline_json) if timeline_json else None
    info = summary.get("match") or {}
    match_id = str(info.get("matchId") or "")
    if not match_id:
        raise IntlParseError("matchId absent")
    millis = (info.get("time") or {}).get("millis")
    if millis is None:
        raise IntlParseError("Coup d'envoi absent")
    kickoff_ts = datetime.fromtimestamp(int(millis) / 1000, tz=UTC)
    season_id = season_for_date(kickoff_ts.date())
    if season_id is None:
        raise IntlParseError(f"Date hors saisons: {kickoff_ts.date()}")
    teams = info.get("teams") or []
    lineups = summary.get("teams") or []
    if len(teams) != 2 or len(lineups) != 2:
        raise IntlParseError("Équipes incomplètes")
    all_secs = [
        int(e["time"]["secs"]) for e in (timeline or {}).get("timeline", []) if e.get("time")
    ]
    match_end = max([FULL_MATCH_SECS, *all_secs])
    appearances: list[dict[str, object]] = []
    for idx, (team, lineup) in enumerate(zip(teams, lineups, strict=True)):
        players = [p for p in (lineup.get("teamList") or {}).get("list", []) if p.get("number")]
        if len([p for p in players if int(p["number"]) <= 15]) != 15:
            raise IntlParseError(f"{team.get('name')}: composition sans 15 titulaires")
        events = _events(timeline, idx)
        for p in players:
            shirt = int(p["number"])
            player_id = str(p["player"]["id"])
            kinds = events.get(player_id, [])
            appearances.append(
                {
                    "source": SOURCE,
                    "source_match_id": match_id,
                    "source_player_id": player_id,
                    "player_name": p["player"]["name"]["display"],
                    "team_name": team["name"],
                    "shirt_number": shirt,
                    "is_starter": shirt <= 15,
                    "position_raw": position_from_shirt(shirt) or "unknown",
                    "minutes_played": None
                    if timeline is None
                    else _minutes(shirt <= 15, kinds, match_end),
                    "yellow_cards": sum(1 for _, k in kinds if k == "Yellow Card"),
                    "red_cards": sum(1 for _, k in kinds if k == "Red Card"),
                }
            )
    scores = info.get("scores") or [None, None]
    venue = info.get("venue") or {}
    match: dict[str, object] = {
        "source": SOURCE,
        "source_match_id": match_id,
        "competition_code": competition_code(str(info.get("competition") or ""), kickoff_ts.date()),
        "season_id": season_id,
        "round": None,
        "kickoff_ts": kickoff_ts,
        "kickoff_time_imputed": False,
        "venue_name": ", ".join(v for v in (venue.get("name"), venue.get("city")) if v) or None,
        "home_team_name": teams[0]["name"],
        "away_team_name": teams[1]["name"],
        "home_score": scores[0],
        "away_score": scores[1],
    }
    StagingMatch.validate(staging_frame("match", [match]))
    StagingAppearance.validate(staging_frame("appearance", appearances))
    return match, appearances
