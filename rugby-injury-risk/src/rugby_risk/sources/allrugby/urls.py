BASE_URL = "https://www.allrugby.com"


# Checked on the live site (2026-11-06): the Top 14 calendar of season 2023-2024 is
# `/competitions/top-14-2024/calendrier.html` (end year); match and player pages are
# linked as `/saison-2023-2024/matchs/{slug}-{id}.html` and `/joueurs/{slug}-{id}.html`.
def season_page_url(season_id: str) -> str:
    return f"{BASE_URL}/competitions/top-14-{season_id.split('-')[1]}/calendrier.html"
