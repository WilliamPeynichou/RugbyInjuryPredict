"""Parse an allrugby player page into a StagingPlayerProfile.

PARSER_VERSION = allrugby-2 (markup checked on real pages, 2026-11-06):
- JSON-LD `Person`: `name`, `nationality`, `birthDate` (year only: not a date, so
  `birth_date` stays null);
- `div.bio p`: `il mesure 196 cm pour 108 kg`, `au poste de 3ème ligne`,
  `est <b>JIFF</b>` (absent for non-JIFF players).
"""

import json
import re

from selectolax.lexbor import LexborHTMLParser

from rugby_risk.staging_schemas import StagingPlayerProfile
from rugby_risk.warehouse import staging_frame

PARSER_VERSION = "allrugby-2"


class PlayerParseError(Exception):
    """A player page has no usable profile."""


def _person(page: LexborHTMLParser) -> dict[str, object]:
    for node in page.css('script[type="application/ld+json"]'):
        try:
            data = json.loads(node.text())
        except ValueError:
            continue
        for item in data.get("@graph", [data]) if isinstance(data, dict) else []:
            if isinstance(item, dict) and item.get("@type") == "Person":
                return item
    raise PlayerParseError("JSON-LD Person absent")


def parse_player(html: str, source_player_id: str) -> dict[str, object]:
    page = LexborHTMLParser(html)
    person = _person(page)
    if not person.get("name"):
        raise PlayerParseError("Nom absent")
    bio_node = page.css_first("div.bio p")
    bio = " ".join(bio_node.text().split()) if bio_node else ""
    height = re.search(r"mesure (\d{3})\s*cm", bio)
    weight = re.search(r"pour (\d{2,3})\s*kg", bio)
    position = re.search(r"au poste de ([^.,]+)", bio)
    profile: dict[str, object] = {
        "source": "allrugby",
        "source_player_id": source_player_id,
        "full_name": str(person["name"]),
        "birth_date": None,
        "height_cm": int(height.group(1)) if height else None,
        "weight_kg": int(weight.group(1)) if weight else None,
        "nationality": person.get("nationality") or None,
        "jiff": ("est JIFF" in bio) if bio else None,
        "positions_raw": position.group(1).strip() if position else None,
    }
    StagingPlayerProfile.validate(staging_frame("player_profile", [profile]))
    return profile
