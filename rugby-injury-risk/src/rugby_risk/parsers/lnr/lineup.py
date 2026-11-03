"""Parse une feuille de match LNR (compositions) en staging.

PARSER_VERSION = lnr-1
Hypothèses de balisage (fixtures figées, à valider au premier crawl autorisé) :
`div.match-sheet` avec `div.comp-header` (span.comp, span.season, span.round,
span.match-id), `h2` (span.home, span.score, span.away), `div.kickoff`,
`div.venue span[itemprop=name]`, puis une `section.team` par équipe dont la
table `table.lineup` contient des `tr.starter` (XV) et `tr.bench` (remplaçants)
avec `td.pos`, `td.player a[href=/joueurs/{slug}-{id}]`, `td.nat`.
La LNR ne donne pas les minutes : `minutes_played = NULL` (composition + ID).
"""

from datetime import UTC, datetime
from pathlib import Path
from zoneinfo import ZoneInfo

import polars as pl
from selectolax.lexbor import LexborHTMLParser, LexborNode

from rugby_risk.warehouse import staging_frame

PARSER_VERSION = "lnr-1"
DEFAULT_KICKOFF_HOUR_LOCAL = 15
ALIASES_PATH = Path("data/reference/position_aliases.csv")
UNKNOWN_POSITION = "unknown"


class LineupParseError(Exception):
    """Une feuille LNR est invalide ; porte la raison de quarantaine."""


def load_position_aliases(path: Path = ALIASES_PATH) -> dict[str, str]:
    frame = pl.read_csv(path)
    return dict(zip(frame["raw_label"].to_list(), frame["position_code"].to_list(), strict=True))


def normalize_position(raw: str, aliases: dict[str, str] | None = None) -> str:
    table = aliases if aliases is not None else load_position_aliases()
    return table.get(raw.strip(), UNKNOWN_POSITION)


def _text(node: LexborNode | None) -> str:
    return node.text(strip=True) if node else ""


def _parse_kickoff(text: str) -> tuple[datetime, bool]:
    for fmt, imputed in (("%d/%m/%Y %H:%M", False), ("%d/%m/%Y", True)):
        try:
            parsed = datetime.strptime(text, fmt)
            local = parsed.replace(hour=DEFAULT_KICKOFF_HOUR_LOCAL) if imputed else parsed
            return local.replace(tzinfo=ZoneInfo("Europe/Paris")).astimezone(UTC), imputed
        except ValueError:
            continue
    raise LineupParseError(f"Coup d'envoi illisible: {text!r}")


def _player_rows(section: LexborNode, team: str) -> list[dict[str, object]]:
    aliases = load_position_aliases()
    rows = []
    for tr in section.css("table.lineup tr"):
        classes = (tr.attributes.get("class") or "").split()
        if "starter" not in classes and "bench" not in classes:
            continue
        link = tr.css_first("td.player a")
        href = (link.attributes.get("href") or "") if link is not None else ""
        player_id = href.rsplit("-", 1)[-1] if href else ""
        raw_position = _text(tr.css_first("td.pos"))
        rows.append(
            {
                "source": "lnr",
                "source_match_id": "",
                "source_player_id": player_id,
                "player_name": _text(link) if link is not None else "",
                "team_name": team,
                "shirt_number": int(tr.attributes.get("data-shirt") or 0),
                "is_starter": "starter" in classes,
                "position_raw": normalize_position(raw_position, aliases),
                "minutes_played": None,
                "yellow_cards": 0,
                "red_cards": 0,
            }
        )
    return rows


def parse_lineup(html: str, season_id: str) -> tuple[dict[str, object], list[dict[str, object]]]:
    page = LexborHTMLParser(html)
    sheet = page.css_first("div.match-sheet")
    if sheet is None:
        raise LineupParseError("div.match-sheet absent")
    home_node, away_node = sheet.css_first("h2 span.home"), sheet.css_first("h2 span.away")
    if home_node is None or away_node is None:
        raise LineupParseError("Titres DOM/EXT absents")
    home_team, away_team = _text(home_node), _text(away_node)
    match_id = _text(sheet.css_first("div.comp-header span.match-id"))
    if not match_id:
        raise LineupParseError("Identifiant de match absent")
    kickoff_ts, imputed = _parse_kickoff(_text(sheet.css_first("div.kickoff")))
    score = _text(sheet.css_first("h2 span.score"))
    sections = sheet.css("section.team")
    if len(sections) != 2:
        raise LineupParseError(f"Feuilles incomplètes: {len(sections)} section(s)")
    appearances: list[dict[str, object]] = []
    for expected, section in zip((home_team, away_team), sections, strict=True):
        team = section.attributes.get("data-team") or ""
        if team != expected:
            raise LineupParseError(f"Feuille {team!r} ≠ titre {expected!r}")
        rows = _player_rows(section, team)
        if len([r for r in rows if r["is_starter"]]) != 15:
            raise LineupParseError(f"{team}: feuille sans 15 titulaires")
        for row in rows:
            row["source_match_id"] = match_id
        appearances.extend(rows)
    match: dict[str, object] = {
        "source": "lnr",
        "source_match_id": match_id,
        "competition_code": "TOP14",
        "season_id": season_id,
        "round": _text(sheet.css_first("div.comp-header span.round")),
        "kickoff_ts": kickoff_ts,
        "kickoff_time_imputed": imputed,
        "venue_name": _text(sheet.css_first("div.venue span[itemprop=name]")),
        "home_team_name": home_team,
        "away_team_name": away_team,
        "home_score": int(score.split("-")[0]) if "-" in score else None,
        "away_score": int(score.split("-")[1]) if "-" in score else None,
    }
    from rugby_risk.staging_schemas import StagingAppearance, StagingMatch  # noqa: PLC0415

    StagingMatch.validate(staging_frame("match", [match]))
    StagingAppearance.validate(staging_frame("appearance", appearances))
    return match, appearances
