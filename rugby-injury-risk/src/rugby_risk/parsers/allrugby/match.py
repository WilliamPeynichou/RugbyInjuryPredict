"""Parse an allrugby match page into a StagingMatch + StagingAppearances.

PARSER_VERSION = allrugby-2 (markup checked on real pages, 2026-11-06; see
tests/fixtures/allrugby/README.md). Page layout:
- `link[rel=canonical]` ends with `-{match_id}.html`;
- `div.pas > div.txtcenter` header: `Date : samedi 27 avril 2024 Coup d'envoi : 17h00
  Stade : ... Competition : Top 14 Phase : poule`;
- `div.match_entete`: two `div.equipe` (home, away) and two `div.score`;
- `table.fdm`: lineup rows of 13 cells (home cards, 4 home scoring cells, home player,
  shirt n°, away player, 4 away scoring cells, away cards), cards as `div.cj|cr|co`
  holding the minute; then substitution rows of 3 cells
  (`HOME remplacé par SUB, 54'` | `#1` | `49', AWAY remplacé par SUB`).
Minutes = time on the field from the substitution timeline over 80', re-entries
included (checked against allrugby player pages); red (cr) or 20-minute red (co)
removes the player from the carding minute.
"""

import re
from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from selectolax.lexbor import LexborHTMLParser, LexborNode

from rugby_risk.reference import position_from_shirt
from rugby_risk.staging_schemas import StagingAppearance, StagingMatch
from rugby_risk.warehouse import staging_frame

PARSER_VERSION = "allrugby-2"
DEFAULT_KICKOFF_HOUR_LOCAL = 15  # heure locale imputée quand la page ne la donne pas
MATCH_MINUTES = 80
REQUIRED_STARTERS = 15
LINEUP_CELLS = 13
SUB_CELLS = 3
HEADER_LABELS = ("Date", "Coup d'envoi", "Stade", "Competition", "Phase")
MONTHS = {
    m: i
    for i, m in enumerate(
        (
            "janvier",
            "février",
            "mars",
            "avril",
            "mai",
            "juin",
            "juillet",
            "août",
            "septembre",
            "octobre",
            "novembre",
            "décembre",
        ),
        start=1,
    )
}
SUB_PATTERN = re.compile(r"(.+?) remplacé par (.+?)$")
MINUTE_PATTERN = re.compile(r"(\d+)'")


class MatchParseError(Exception):
    """A match page is not a valid team sheet; carries the quarantine reason."""


def _text(node: LexborNode | None) -> str:
    return " ".join(node.text().split()) if node else ""


def _header(page: LexborHTMLParser) -> dict[str, str]:
    text = _text(page.css_first("div.pas div.txtcenter"))
    labels = "|".join(re.escape(label) for label in HEADER_LABELS)
    parts = re.split(rf"({labels}) :", text)
    return {parts[i]: parts[i + 1].strip() for i in range(1, len(parts) - 1, 2)}


def _parse_kickoff(day: str, time: str) -> tuple[datetime, bool]:
    match = re.search(r"(\d{1,2}) (\w+) (\d{4})", day)
    if match is None or match.group(2).lower() not in MONTHS:
        raise MatchParseError(f"Date illisible: {day!r}")
    clock = re.fullmatch(r"(\d{1,2})h(\d{2})", time)
    hour, minute = (int(clock.group(1)), int(clock.group(2))) if clock else (15, 0)
    local = datetime(
        int(match.group(3)),
        MONTHS[match.group(2).lower()],
        int(match.group(1)),
        hour if clock else DEFAULT_KICKOFF_HOUR_LOCAL,
        minute,
        tzinfo=ZoneInfo("Europe/Paris"),
    )
    return local.astimezone(UTC), clock is None


def _cards(cell: LexborNode) -> tuple[int, int, int | None]:
    """(yellow, red, minute of the first red) from a `div.cartons` cell."""
    yellow = len(cell.css("div.cj"))
    reds = cell.css("div.cr") + cell.css("div.co")
    minutes = [int(m.group(1)) for n in reds if (m := MINUTE_PATTERN.search(n.text()))]
    return yellow, len(reds), min(minutes) if minutes else None


def _player(cell: LexborNode) -> tuple[str, str] | None:
    link = cell.css_first("a")
    href = (link.attributes.get("href") or "") if link is not None else ""
    found = re.search(r"-(\d+)\.html$", href)
    return (_text(link), found.group(1)) if link is not None and found else None


def _surname(name: str) -> str:
    """Upper-case tokens of the display name, as used in substitution rows."""
    tokens = [t for t in name.split() if t.upper() == t and any(c.isalpha() for c in t)]
    return " ".join(tokens) or name.upper()


def _substitution(text: str) -> tuple[str, str, int] | None:
    minute = MINUTE_PATTERN.search(text)
    names = MINUTE_PATTERN.sub("", text).strip(" ,")
    found = SUB_PATTERN.match(names)
    if minute is None or found is None:
        return None
    return found.group(1).strip(), found.group(2).strip(), int(minute.group(1))


def _minutes(
    players: list[dict[str, object]], subs: list[tuple[str, str, int]]
) -> dict[int, int | None]:
    """Minutes per shirt number from the timeline; None when a name is ambiguous."""
    by_name: dict[str, list[int]] = {}
    for p in players:
        by_name.setdefault(_surname(str(p["player_name"])), []).append(int(str(p["shirt"])))
    ambiguous = {n for name, shirts in by_name.items() if len(shirts) > 1 for n in shirts}
    on = {int(str(p["shirt"])): 0 for p in players if int(str(p["shirt"])) <= REQUIRED_STARTERS}
    total = {int(str(p["shirt"])): 0 for p in players}
    for off_name, in_name, minute in sorted(subs, key=lambda s: s[2]):
        off, sub = by_name.get(off_name, []), by_name.get(in_name, [])
        if len(off) == 1 and off[0] in on:
            total[off[0]] += minute - on.pop(off[0])
        if len(sub) == 1 and sub[0] not in on:
            on[sub[0]] = minute
    for p in players:
        red = p["red_minute"]
        shirt = int(str(p["shirt"]))
        if isinstance(red, int) and shirt in on:
            total[shirt] += max(red - on.pop(shirt), 0)
    for shirt, start in on.items():
        total[shirt] += MATCH_MINUTES - start
    return {s: (None if s in ambiguous else min(m, MATCH_MINUTES)) for s, m in total.items()}


def _sheet(
    table: LexborNode,
) -> tuple[list[dict[str, object]], list[dict[str, object]], list[list[tuple[str, str, int]]]]:
    home: list[dict[str, object]] = []
    away: list[dict[str, object]] = []
    subs: tuple[list[tuple[str, str, int]], list[tuple[str, str, int]]] = ([], [])
    for tr in table.css("tbody tr"):
        cells = tr.css("td")
        if len(cells) == LINEUP_CELLS and _text(cells[6]).isdigit():
            shirt = int(_text(cells[6]))
            cells_sides = ((home, cells[5], cells[0]), (away, cells[7], cells[12]))
            for side, name_cell, card_cell in cells_sides:
                player = _player(name_cell)
                if player is not None:
                    yellow, red, red_minute = _cards(card_cell)
                    side.append(
                        {
                            "player_name": player[0],
                            "source_player_id": player[1],
                            "shirt": shirt,
                            "yellow": yellow,
                            "red": red,
                            "red_minute": red_minute,
                        }
                    )
        elif len(cells) == SUB_CELLS:
            for i, cell in ((0, cells[0]), (1, cells[2])):
                sub = _substitution(_text(cell))
                if sub is not None:
                    subs[i].append(sub)
    return home, away, list(subs)


def parse_match(html: str, season_id: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    page = LexborHTMLParser(html)
    header = _header(page)
    if "Date" not in header:
        raise MatchParseError("En-tête de match absent")
    if header.get("Competition") != "Top 14":
        raise MatchParseError(f"Compétition hors Top 14: {header.get('Competition')!r}")
    canonical = page.css_first("link[rel=canonical]")
    href = (canonical.attributes.get("href") or "") if canonical else ""
    found = re.search(r"-(\d+)\.html$", href)
    if found is None:
        raise MatchParseError("Identifiant de match absent")
    match_id = found.group(1)
    teams = [_text(n) for n in page.css("div.match_entete div.equipe")]
    scores = [_text(n) for n in page.css("div.match_entete div.score")]
    if len(teams) != 2 or len(scores) != 2:
        raise MatchParseError("Équipes ou score absents")
    table = page.css_first("table.fdm")
    if table is None:
        raise MatchParseError("Feuille de match absente")
    home, away, subs = _sheet(table)
    kickoff_ts, imputed = _parse_kickoff(header["Date"], header.get("Coup d'envoi", ""))
    phase = header.get("Phase", "")
    day = re.search(r"journée (\d+)", _text(page.css_first("div.grid-2")))
    appearances = []
    sheets = ((teams[0], home, subs[0]), (teams[1], away, subs[1]))
    for team, players, team_subs in sheets:
        starters = [p for p in players if int(str(p["shirt"])) <= REQUIRED_STARTERS]
        if len(starters) != REQUIRED_STARTERS:
            raise MatchParseError(f"{team}: feuille sans 15 titulaires")
        minutes = _minutes(players, team_subs)
        for p in players:
            shirt = int(str(p["shirt"]))
            appearances.append(
                {
                    "source": "allrugby",
                    "source_match_id": match_id,
                    "source_player_id": p["source_player_id"],
                    "player_name": p["player_name"],
                    "team_name": team,
                    "shirt_number": shirt,
                    "is_starter": shirt <= REQUIRED_STARTERS,
                    "position_raw": position_from_shirt(shirt) or "unknown",
                    "minutes_played": minutes[shirt],
                    "yellow_cards": p["yellow"],
                    "red_cards": p["red"],
                }
            )
    match = {
        "source": "allrugby",
        "source_match_id": match_id,
        "competition_code": "TOP14",
        "season_id": season_id,
        "round": f"J{day.group(1)}" if phase.lower() == "poule" and day else phase or None,
        "kickoff_ts": kickoff_ts,
        "kickoff_time_imputed": imputed,
        "venue_name": header.get("Stade") or None,
        "home_team_name": teams[0],
        "away_team_name": teams[1],
        "home_score": int(scores[0]) if scores[0].isdigit() else None,
        "away_score": int(scores[1]) if scores[1].isdigit() else None,
    }
    StagingMatch.validate(staging_frame("match", [match]))
    StagingAppearance.validate(staging_frame("appearance", appearances))
    return match, appearances
