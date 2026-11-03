"""Parse an allrugby match page into a StagingMatch + StagingAppearances.

PARSER_VERSION = allrugby-1
Page assumptions (built from the documented public format; see tests/fixtures/allrugby/README.md):
one `table.club_stats` per team, caption `Club — CITY`, body rows
`td.n | td.player-name (a href /joueurs/slug-ID.html) | td.minutes | td.card`
("jaune" / "rouge" / "2jaunes"), and a `div.matchinfo` header with
`span.competition-seo`, `span.season`, `span.round`, `span.match-id`,
`div.venue span[itemprop=name]`, `span.kickoff` (dd/mm/yyyy [hh:mm]) and `span.score`.
"""

from datetime import UTC, datetime
from zoneinfo import ZoneInfo

from selectolax.lexbor import LexborHTMLParser, LexborNode

from rugby_risk.staging_schemas import StagingAppearance, StagingMatch
from rugby_risk.warehouse import staging_frame

PARSER_VERSION = "allrugby-1"
DEFAULT_KICKOFF_HOUR_LOCAL = 15  # heure locale imputée quand la page ne la donne pas
DEFAULT_POSITION = "unknown"
REQUIRED_STARTERS = 15


def _text(node: LexborNode | None) -> str:
    return node.text(strip=True) if node else ""


def _int(value: str) -> int | None:
    value = value.strip()
    head = value.split("(")[0].strip()  # ex. "12 (2e jaune)" -> "12"
    return int(head) if head.isdigit() else None


class MatchParseError(Exception):
    """A match page is not a valid team sheet; carries the quarantine reason."""


def _team_rows(table: LexborNode) -> tuple[str, str, list[tuple[int, str, str, int, str]]]:
    rows: list[tuple[int, str, str, int, str]] = []
    caption = _text(table.css_first("caption"))
    parts = caption.split(" — ")
    team, city = parts[0], (parts[1] if len(parts) > 1 else caption)
    for tr in table.css("tbody tr"):
        cells = tr.css("td")
        if len(cells) < 4:
            continue
        num = _int(cells[0].text())
        link = cells[1].css_first("a")
        href = (link.attributes.get("href") or "") if link is not None else ""
        if num is not None and link is not None:
            rows.append(
                (num, _text(cells[1]), href, _int(cells[2].text()) or 0, _text(cells[3]).lower())
            )
    return team, city, rows


def _parse_kickoff(text: str) -> tuple[datetime, bool]:
    for fmt, imputed in (("%d/%m/%Y %H:%M", False), ("%d/%m/%Y", True)):
        try:
            parsed = datetime.strptime(text, fmt)
            local = parsed.replace(hour=DEFAULT_KICKOFF_HOUR_LOCAL) if imputed else parsed
            return local.replace(tzinfo=ZoneInfo("Europe/Paris")).astimezone(UTC), imputed
        except ValueError:
            continue
    raise MatchParseError(f"Kickoff illisible: {text!r}")


def _cards(card: str) -> tuple[int, int]:
    return (1 if card in {"jaune", "2jaunes"} else 0, 1 if card == "rouge" else 0)


def parse_match(html: str, season_id: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    page = LexborHTMLParser(html)
    info = page.css_first("div.matchinfo")
    if info is None:
        raise MatchParseError("div.matchinfo absent")
    home_node, away_node = info.css_first("h2 span.home"), info.css_first("h2 span.away")
    if home_node is None or away_node is None:
        raise MatchParseError("Titre 'DOM EXT' absent")
    home_team, away_team = _text(home_node), _text(away_node)
    if not _text(info.css_first("span.competition-seo")).startswith("top14"):
        raise MatchParseError("Compétition hors Top 14")
    match_id = _text(info.css_first("span.match-id"))
    if not match_id:
        raise MatchParseError("Identifiant de match absent")
    kickoff_ts, imputed = _parse_kickoff(_text(info.css_first("span.kickoff")))
    venue = _text(info.css_first("div.venue span[itemprop=name]"))
    score = _text(info.css_first("span.score"))
    if "-" not in score:
        raise MatchParseError(f"Score illisible: {score!r}")
    home_score, away_score = (int(part) for part in score.split("-"))
    tables = page.css("table.club_stats")
    if len(tables) != 2:
        raise MatchParseError(f"Feuilles incomplètes: {len(tables)} table(s)")
    appearances = []
    home_city = ""
    for expected, table in zip((home_team, away_team), tables, strict=True):
        team, city, rows = _team_rows(table)
        if not home_city:
            home_city = city
        if team != expected:
            raise MatchParseError(f"Feuille {team!r} ≠ titre {expected!r}")
        if len([r for r in rows if r[0] <= 15]) != REQUIRED_STARTERS:
            raise MatchParseError(f"{team}: feuille sans 15 titulaires")
        for num, name, href, minutes, card in rows:
            yellow, red = _cards(card)
            appearances.append(
                {
                    "source": "allrugby",
                    "source_match_id": match_id,
                    "source_player_id": href.rsplit("-", 1)[-1].removesuffix(".html"),
                    "player_name": name,
                    "team_name": team,
                    "shirt_number": num,
                    "is_starter": num <= 15,
                    "position_raw": DEFAULT_POSITION,
                    "minutes_played": minutes,
                    "yellow_cards": yellow,
                    "red_cards": red,
                }
            )
    match = {
        "source": "allrugby",
        "source_match_id": match_id,
        "competition_code": "TOP14",
        "season_id": season_id,
        "round": _text(info.css_first("span.round")),
        "kickoff_ts": kickoff_ts,
        "kickoff_time_imputed": imputed,
        "venue_name": f"{venue}, {home_city}" if venue and home_city else venue,
        "home_team_name": home_team,
        "away_team_name": away_team,
        "home_score": home_score,
        "away_score": away_score,
    }
    StagingMatch.validate(staging_frame("match", [match]))
    StagingAppearance.validate(staging_frame("appearance", appearances))
    return match, appearances
