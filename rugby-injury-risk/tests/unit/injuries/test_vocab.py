import re
from pathlib import Path

from rugby_risk.injuries.vocab import BodyRegion, InjuryType

DOC = Path("docs/04-data-model.md")


def _doc_list(field: str) -> set[str]:
    text = DOC.read_text(encoding="utf-8")
    match = re.search(rf"{field}\s+TEXT,\s*--\s*([a-z_ |]+)", text)
    assert match, field
    return {token.strip() for token in match.group(1).split("|")}


def test_body_region_matches_docs_04():
    assert {r.value for r in BodyRegion} == _doc_list("body_region")


def test_injury_type_matches_docs_04():
    assert {r.value for r in InjuryType} == _doc_list("injury_type")
