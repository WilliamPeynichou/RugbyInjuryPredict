import pytest

from rugby_risk.sources.allrugby.fetch import (
    PLAYER_PATH_PATTERN,
    collect_paths,
    match_path_pattern,
)
from rugby_risk.sources.allrugby.urls import season_page_url

pytestmark = pytest.mark.unit
FIXTURES = "tests/fixtures/allrugby"


def test_season_url_uses_end_year():
    assert season_page_url("2023-2024").endswith("/competitions/top-14-2024/calendrier.html")


def test_calendar_lists_regular_season_and_playoffs():
    with open(f"{FIXTURES}/calendar_top14_2024.html", encoding="utf-8") as fh:
        html = fh.read()
    paths = collect_paths(html, match_path_pattern("2023-2024"))
    assert len(paths) == 188  # 182 journées + barrages, demies, finale, access match
    assert "/saison-2023-2024/matchs/toulouse-bordeaux-21156.html" in paths


def test_match_page_lists_46_players():
    with open(f"{FIXTURES}/match_standard.html", encoding="utf-8") as fh:
        html = fh.read()
    assert len(collect_paths(html, PLAYER_PATH_PATTERN)) == 46
