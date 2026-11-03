BASE_URL = "https://top14.lnr.fr"


def slug(name: str) -> str:
    return name.lower().replace(" ", "-").replace("è", "e").replace("é", "e")


def calendar_url(season_id: str) -> str:
    return f"{BASE_URL}/calendrier/{season_id}"


def lineup_url(season_id: str, round_id: str, match_id: str, home: str, away: str) -> str:
    # Forme documentée : feuille-de-match/{saison}/j{journée}/{id}-{dom}-{ext}/compositions
    return (
        f"{BASE_URL}/feuille-de-match/{season_id}/{round_id.lower()}/"
        f"{match_id}-{slug(home)}-{slug(away)}/compositions"
    )
