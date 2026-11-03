"""Parse an allrugby player page into a StagingPlayerProfile.

PARSER_VERSION = allrugby-1
Assumptions (see tests/fixtures/allrugby/README.md): `h1[itemprop=name]`,
`ul.fiche li` lines `label : value` with labels Naissance / Taille / Poids /
Nationalité / JIFF / Sélections.
"""

import re
from datetime import date, datetime

from selectolax.lexbor import LexborHTMLParser

from rugby_risk.staging_schemas import StagingPlayerProfile
from rugby_risk.warehouse import staging_frame

PARSER_VERSION = "allrugby-1"
PLAYER_ID_PATTERN = re.compile(r"-(\d+)\.html$")


class PlayerParseError(Exception):
    """A player page has no usable profile."""


def parse_player(html: str, source_player_id: str) -> dict[str, object]:
    page = LexborHTMLParser(html)
    name_node = page.css_first("h1[itemprop=name]")
    if name_node is None:
        raise PlayerParseError("h1[itemprop=name] absent")
    fields = {}
    for li in page.css("ul.fiche li"):
        text = li.text(strip=True)
        if " : " in text:
            label, value = text.split(" : ", 1)
            fields[label.strip()] = value.strip()
    birth = fields.get("Naissance", "")
    profile: dict[str, object] = {
        "source": "allrugby",
        "source_player_id": source_player_id,
        "full_name": name_node.text(strip=True),
        "birth_date": _parse_birth(birth),
        "height_cm": _parse_cm(fields.get("Taille", "")),
        "weight_kg": _parse_int(fields.get("Poids", "")),
        "nationality": fields.get("Nationalité") or None,
        "jiff": _parse_jiff(fields.get("JIFF", "")),
        "positions_raw": fields.get("Postes") or None,
    }
    StagingPlayerProfile.validate(staging_frame("player_profile", [profile]))
    return profile


def _parse_birth(value: str) -> date | None:
    match = re.search(r"(\d{2}/\d{2}/\d{4})", value)
    if not match:
        return None
    return datetime.strptime(match.group(1), "%d/%m/%Y").date()


def _parse_cm(value: str) -> int | None:
    match = re.search(r"(\d+(?:[.,]\d+)?)\s*m", value)
    return round(float(match.group(1).replace(",", ".")) * 100) if match else None


def _parse_int(value: str) -> int | None:
    match = re.search(r"(\d+)", value)
    return int(match.group(1)) if match else None


def _parse_jiff(value: str) -> bool | None:
    if not value:
        return None
    return "oui" in value.lower()
