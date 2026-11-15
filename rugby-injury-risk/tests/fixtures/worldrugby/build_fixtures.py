"""Build anonymized international fixtures (World Rugby + ESPN). Run: python build_fixtures.py.

Shapes follow src/rugby_risk/sources/{worldrugby,espn}/README.md. Players are fictional.
"""

import json
from datetime import UTC, datetime
from pathlib import Path

HERE = Path(__file__).resolve().parent
WR, ESPN = HERE.parent / "worldrugby", HERE.parent / "espn"


def pid(team: str, shirt: int) -> str:
    return f"{team[:3].lower()}-{shirt}"


def wr_lineup(team: str, size: int = 23) -> dict:
    return {
        "teamList": {
            "list": [
                {
                    "number": str(n),
                    "player": {"id": pid(team, n), "name": {"display": f"Joueur {team} {n}"}},
                }
                for n in range(1, size + 1)
            ]
        }
    }


def wr_summary(
    match_id: str,
    comp: str,
    kickoff: datetime,
    home: str,
    away: str,
    scores: list[int],
    lineups: list[dict],
) -> dict:
    return {
        "match": {
            "matchId": match_id,
            "matchAltId": f"alt-{match_id}",
            "competition": comp,
            "status": "C",
            "time": {
                "millis": int(kickoff.timestamp() * 1000),
                "label": kickoff.date().isoformat(),
            },
            "venue": {"name": "Stade Fictif", "city": "Ville", "country": home},
            "teams": [{"id": "1", "name": home}, {"id": "2", "name": away}],
            "scores": scores,
        },
        "teams": lineups,
    }


def ev(kind: str, team_idx: int, player: str, minute: int) -> dict:
    return {"type": kind, "teamIndex": team_idx, "playerId": player, "time": {"secs": minute * 60}}


def espn_roster(side: str, team: str, size: int) -> dict:
    return {
        "homeAway": side,
        "team": {"displayName": team},
        "roster": [
            {
                "jersey": str(n),
                "starter": False,
                "athlete": {"id": f"e-{pid(team, n)}", "displayName": f"Joueur {team} {n}"},
            }
            for n in range(1, size + 1)
        ],
    }


def espn_summary(
    event_id: str,
    league: str,
    kickoff: str,
    home: str,
    away: str,
    rosters: list[dict],
    extra: dict | None = None,
) -> dict:
    return {
        "header": {
            "id": event_id,
            "league": {"name": league},
            **(extra or {}),
            "competitions": [
                {
                    **({"notes": extra["notes"]} if extra and "notes" in extra else {}),
                    "date": kickoff,
                    "competitors": [
                        {"homeAway": "home", "team": {"displayName": home}, "score": "27"},
                        {"homeAway": "away", "team": {"displayName": away}, "score": "13"},
                    ],
                }
            ],
        },
        "gameInfo": {"venue": {"fullName": "Stade Fictif"}},
        "rosters": rosters,
    }


def dump(path: Path, data: dict) -> None:
    path.write_text(json.dumps(data, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")


def main() -> None:
    WR.mkdir(exist_ok=True)
    ESPN.mkdir(exist_ok=True)
    fra, irl, nzl = "France", "Ireland", "New Zealand"
    # Six Nations : remplacement simple (50'), IR (20'), jaune, essai ignoré.
    dump(
        WR / "six_nations_summary.json",
        wr_summary(
            "wr-6n-01",
            "Six Nations 2024",
            datetime(2024, 2, 2, 20, tzinfo=UTC),
            fra,
            irl,
            [17, 38],
            [wr_lineup(fra), wr_lineup(irl)],
        ),
    )
    dump(
        WR / "six_nations_timeline.json",
        {
            "timeline": [
                ev("Sub Off", 0, pid(fra, 1), 50),
                ev("Sub On", 0, pid(fra, 17), 50),
                ev("IR", 0, pid(fra, 4), 20),
                ev("IR", 0, pid(fra, 19), 20),
                ev("Yellow Card", 0, pid(fra, 6), 33),
                ev("Try", 0, pid(fra, 11), 40),
            ]
        },
    )
    # Test de novembre (libellé générique -> mois) : rouge à 60' sans remplaçant.
    dump(
        WR / "november_test_summary.json",
        wr_summary(
            "wr-nov-01",
            "International Test Match",
            datetime(2024, 11, 16, 20, 10, tzinfo=UTC),
            fra,
            nzl,
            [30, 29],
            [wr_lineup(fra), wr_lineup(nzl)],
        ),
    )
    dump(WR / "november_test_timeline.json", {"timeline": [ev("Red Card", 1, pid(nzl, 5), 60)]})
    # Coupe du monde : rouge à 10' (écart minutes > 5 %), présent aussi côté ESPN.
    dump(
        WR / "rwc_summary.json",
        wr_summary(
            "wr-rwc-01",
            "Rugby World Cup 2023",
            datetime(2023, 9, 8, 19, 15, tzinfo=UTC),
            fra,
            nzl,
            [27, 13],
            [wr_lineup(fra), wr_lineup(nzl)],
        ),
    )
    dump(WR / "rwc_timeline.json", {"timeline": [ev("Red Card", 0, pid(fra, 12), 10)]})
    # JSON incomplet : compositions vides.
    dump(
        WR / "incomplete_summary.json",
        wr_summary(
            "wr-inc-01",
            "Six Nations 2024",
            datetime(2024, 2, 10, 15, tzinfo=UTC),
            irl,
            fra,
            [0, 0],
            [{"teamList": {"list": []}}, {"teamList": {"list": []}}],
        ),
    )
    # ESPN : même match de Coupe du monde, un remplaçant manquant côté visiteur.
    dump(
        ESPN / "rwc_summary.json",
        espn_summary(
            "900001",
            "Rugby World Cup",
            "2023-09-08T19:15Z",
            fra,
            nzl,
            [espn_roster("home", fra, 23), espn_roster("away", nzl, 22)],
        ),
    )
    dump(
        ESPN / "incomplete_summary.json",
        espn_summary("900002", "Rugby World Cup", "2023-09-09T19:15Z", irl, fra, []),
    )

    europe()


def board_event(event_id: str, date: str, home: str, away: str, venue: str, week: int) -> dict:
    return {
        "id": event_id,
        "date": date,
        "week": {"number": week},
        "status": {"type": {"completed": False}},
        "competitions": [
            {
                "venue": {"fullName": venue},
                "competitors": [
                    {"homeAway": "home", "team": {"displayName": home}},
                    {"homeAway": "away", "team": {"displayName": away}},
                ],
            }
        ],
    }


def europe() -> None:
    """F08 : poule Champions Cup, quart Challenge Cup, match sans club français, calendrier."""

    def rosters(home: str, away: str) -> list[dict]:
        return [espn_roster("home", home, 23), espn_roster("away", away, 23)]

    dump(
        ESPN / "champions_cup_pool.json",
        espn_summary(
            "910001",
            "Investec Champions Cup",
            "2024-01-13T17:30Z",
            "Toulouse",
            "Harlequins",
            rosters("Toulouse", "Harlequins"),
            {"week": {"number": 2}},
        ),
    )
    dump(
        ESPN / "challenge_cup_qf.json",
        espn_summary(
            "910002",
            "EPCR Challenge Cup",
            "2024-04-12T19:00Z",
            "Clermont Auvergne",
            "Benetton",
            rosters("Clermont Auvergne", "Benetton"),
            {"notes": [{"headline": "Quarter-final"}]},
        ),
    )
    dump(
        ESPN / "champions_cup_no_french.json",
        espn_summary(
            "910003",
            "Investec Champions Cup",
            "2024-01-14T15:00Z",
            "Leinster",
            "Harlequins",
            rosters("Leinster", "Harlequins"),
            {"week": {"number": 2}},
        ),
    )
    # Page calendrier : le match de poule (même heure) + un match à venir.
    dump(
        ESPN / "scoreboard_champions_cup.json",
        {
            "leagues": [{"name": "Investec Champions Cup"}],
            "events": [
                board_event(
                    "910001",
                    "2024-01-13T17:30Z",
                    "Toulouse",
                    "Harlequins",
                    "Stade Ernest Wallon",
                    2,
                ),
                board_event(
                    "910004",
                    "2024-04-06T14:00Z",
                    "La Rochelle",
                    "Leinster",
                    "Stade Marcel Deflandre",
                    5,
                ),
            ],
        },
    )


if __name__ == "__main__":
    main()
