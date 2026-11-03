BASE_URL = "https://www.allrugby.com"


# URL forms verified in docs/01-data-sources.md: `joueurs/{slug}-{id}.html`.
# Competition/match URL slugs are NOT publicly documented: the patterns below
# shortcut: are assumptions to confirm on the first authorized crawl (journal).
def season_page_url(season_id: str) -> str:
    return f"{BASE_URL}/competition/{season_id.replace('-', '-')}"


def match_page_url(match_id: str) -> str:
    return f"{BASE_URL}/matches/{match_id}"


def player_page_url(player_id: str) -> str:
    return f"{BASE_URL}/joueurs/x-{player_id}.html"
