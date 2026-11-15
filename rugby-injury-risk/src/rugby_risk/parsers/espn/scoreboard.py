"""ESPN `scoreboard` page = calendar: every event of a league, played or not, no lineups."""

import json
from datetime import datetime

from rugby_risk.config.seasons import season_for_date
from rugby_risk.parsers.espn.summary import SOURCE, phase
from rugby_risk.parsers.intl import IntlParseError, competition_code
from rugby_risk.staging_schemas import StagingMatch
from rugby_risk.warehouse import staging_frame


def parse_scoreboard(payload: str) -> list[dict[str, object]]:
    """Staging match rows (scores NULL); events out of scope or incomplete are skipped."""
    data = json.loads(payload)
    league = str(((data.get("leagues") or [{}])[0]).get("name") or "")
    rows: list[dict[str, object]] = []
    for event in data.get("events") or []:
        competition = (event.get("competitions") or [{}])[0]
        sides = {c.get("homeAway"): c for c in competition.get("competitors", [])}
        if set(sides) != {"home", "away"} or not event.get("date"):
            continue
        kickoff_ts = datetime.fromisoformat(str(event["date"]).replace("Z", "+00:00"))
        season_id = season_for_date(kickoff_ts.date())
        try:
            code = competition_code(league, kickoff_ts.date())
        except IntlParseError:
            return []  # une page = une ligue : ligue hors périmètre
        if season_id is None:
            continue
        rows.append(
            {
                "source": SOURCE,
                "source_match_id": str(event["id"]),
                "competition_code": code,
                "season_id": season_id,
                "round": phase(event),
                "kickoff_ts": kickoff_ts,
                "kickoff_time_imputed": False,
                "venue_name": (competition.get("venue") or {}).get("fullName"),
                "home_team_name": sides["home"]["team"]["displayName"],
                "away_team_name": sides["away"]["team"]["displayName"],
                "home_score": None,
                "away_score": None,
            }
        )
    StagingMatch.validate(staging_frame("match", rows))
    return rows
