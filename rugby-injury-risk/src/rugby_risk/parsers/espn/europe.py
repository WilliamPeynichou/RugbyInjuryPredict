"""European cups (Champions Cup, Challenge Cup) from ESPN summaries.

Decision F08: ESPN rather than allrugby, the summary parser already exists and covers both
cups with lineups; allrugby's parser is Top 14 only.
"""

from rugby_risk.parsers.espn.summary import SOURCE, parse_summary
from rugby_risk.reference import is_french_club, team_canonical

EUROPE = ("CHAMPIONS_CUP", "CHALLENGE_CUP")


def parse_europe(payload: str) -> tuple[dict[str, object], list[dict[str, object]]] | None:
    """Parsed match if it is a European cup game with at least one Top 14 club, else None.

    Malformed payloads still raise IntlParseError (quarantine).
    """
    match, appearances = parse_summary(payload)
    if match["competition_code"] not in EUROPE:
        return None
    # Depuis 2014, les clubs français engagés en coupe d'Europe viennent du Top 14.
    teams = (str(match["home_team_name"]), str(match["away_team_name"]))
    if not any(is_french_club(team_canonical(team, SOURCE)) for team in teams):
        return None
    return match, appearances
