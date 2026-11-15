"""Independent pure-Python implementation of the F17 features (leakage oracle, docs/05 §8).

For one (player, match) row it loads only the events whose kickoff is strictly before
`as_of_ts = kickoff_ts - 1 s`, then applies the docs/05 definitions literally. The leakage
test compares it with the dbt table: any divergence means the SQL looked at the future
(or that the two readings of the spec differ, which is just as much a bug).
"""

import itertools
import statistics
from collections import defaultdict
from dataclasses import dataclass
from datetime import date, datetime, timedelta
from typing import Any

import duckdb

from rugby_risk.features.registry import EWMA_HALF_LIVES, INJURY_CONF_THRESHOLD, NO_HISTORY

CLUB_LEVELS = ("club_domestic", "club_europe")
SHORT_TURNAROUND_DAYS = 5
RECENT_RETURN_DAYS = 56
HEAVY_MINUTES = 60
FULL_MATCH = 80.0
SEASON_PERIODS = (
    (date(2017, 7, 1), "pre_2017"),
    (date(2018, 7, 1), "2017_2018"),
    (date(2026, 7, 1), "2018_2026"),
)


@dataclass(frozen=True)
class Event:
    match_id: int
    team_id: int
    kickoff: datetime
    day: date
    season_id: str
    level: str
    on_sheet: bool
    played: bool
    is_starter: bool
    minutes: int


@dataclass(frozen=True)
class Match:
    match_id: int
    competition_code: str
    season_id: str
    kickoff: datetime
    day: date
    venue_id: int | None
    home: int
    away: int
    home_score: int | None
    away_score: int | None
    is_playoff: bool


@dataclass(frozen=True)
class Injury:
    onset: date
    return_date: date | None
    concussion: bool


def _rows(con: duckdb.DuckDBPyConnection, sql: str) -> list[tuple[Any, ...]]:
    return con.execute(sql).fetchall()


def _points(scored: int, conceded: int) -> int:
    if scored > conceded:
        return 4
    if scored == conceded:
        return 2
    return 1 if conceded - scored <= 5 else 0  # noqa: PLR2004 - bonus défensif Top 14


def _median(values: list[float]) -> float | None:
    return statistics.median(values) if values else None


class Reference:
    """Loads the marts once, then recomputes the features of any (player, match) row."""

    def __init__(
        self, con: duckdb.DuckDBPyConnection, threshold: float = INJURY_CONF_THRESHOLD
    ) -> None:
        levels = dict(_rows(con, "select competition_code, level from ref_competitions"))
        self.matches: dict[int, Match] = {}
        for r in _rows(
            con,
            """select match_id, competition_code, season_id, kickoff_ts, venue_id,
            home_team_id, away_team_id, home_score, away_score, is_playoff from fact_match""",
        ):
            self.matches[r[0]] = Match(
                r[0], r[1], r[2], r[3], r[3].date(), r[4], r[5], r[6], r[7], r[8], bool(r[9])
            )
        self.events: dict[int, list[Event]] = defaultdict(list)
        for r in _rows(
            con,
            """select e.player_id, e.match_id, e.team_id, e.on_sheet, coalesce(e.played, false),
            coalesce(a.is_starter, false), a.minutes_played
            from fact_eligibility e left join fact_appearance a using (match_id, player_id)""",
        ):
            m = self.matches[r[1]]
            played = bool(r[4])
            self.events[r[0]].append(
                Event(
                    match_id=r[1],
                    team_id=r[2],
                    kickoff=m.kickoff,
                    day=m.day,
                    season_id=m.season_id,
                    level=levels[m.competition_code],
                    on_sheet=bool(r[3]),
                    played=played,
                    is_starter=bool(r[5]),
                    minutes=(r[6] or 0) if played else 0,
                )
            )
        for evs in self.events.values():
            evs.sort(key=lambda e: (e.kickoff, e.match_id))
        self.injuries: dict[int, list[Injury]] = defaultdict(list)
        for r in _rows(
            con,
            f"""select player_id, onset_date, return_date, coalesce(is_concussion, false)
            from fact_injury_event where source_confidence >= {float(threshold)}""",
        ):
            self.injuries[r[0]].append(Injury(r[1], r[2], bool(r[3])))
        self.players = {
            r[0]: r[1:]
            for r in _rows(
                con,
                """select player_id, birth_date, height_cm, weight_kg,
                coalesce(primary_position, 'UNKNOWN'), position_group, unit, full_name
                from dim_player""",
            )
        }
        self._medians()
        self.season_start = dict(_rows(con, "select season_id, start_date from ref_seasons"))
        self.windows = _rows(con, "select start_date, end_date from ref_test_windows")
        self.regimes = _rows(con, "select regime, start_date, end_date from ref_rules_protection")
        self.protected = set(_rows(con, "select season_id, player_name from ref_protected_players"))
        self.surface = {
            (r[0], r[1]): r[2]
            for r in _rows(con, "select venue_id, season_id, surface from ref_venue_surface")
        }

    def _medians(self) -> None:
        by_pos: dict[str, dict[str, list[float]]] = defaultdict(lambda: defaultdict(list))
        for _, h, w, pos, *_ in self.players.values():
            for key, val in (("h", h), ("w", w)):
                if val is not None:
                    by_pos[pos][key].append(float(val))
                    by_pos["*"][key].append(float(val))
            if h is not None and w is not None:
                bmi = w / (h / 100) ** 2
                by_pos[pos]["bmi"].append(bmi)
                by_pos["*"]["bmi"].append(bmi)
        self.median: dict[tuple[str, str], float | None] = {
            (pos, key): _median(vals[key]) for pos, vals in by_pos.items() for key in vals
        }

    def _med(self, pos: str, key: str) -> float | None:
        own = self.median.get((pos, key))
        return own if own is not None else self.median.get(("*", key))

    def features(self, player_id: int, match_id: int) -> dict[str, object]:
        m = self.matches[match_id]
        as_of = m.kickoff - timedelta(seconds=1)
        d = m.day
        team = next(e.team_id for e in self.events[player_id] if e.match_id == match_id)
        past = [e for e in self.events[player_id] if e.kickoff < as_of]
        out: dict[str, object] = {}
        out |= self._load(past, d, self.season_start[m.season_id])
        out |= self._sequence(past, d, m.season_id)
        out |= self._international(past, d, player_id, m.season_id)
        out |= self._history(player_id, past, d)
        out |= self._player(player_id, past, d, m.season_id)
        out |= self._context(m, team, as_of)
        return out

    @staticmethod
    def _load(past: list[Event], d: date, season_start: date) -> dict[str, object]:
        year = [e for e in past if d - timedelta(days=365) <= e.day < d and e.played]

        def minutes(days: int, levels: tuple[str, ...] | None = None) -> int:
            return sum(
                e.minutes
                for e in year
                if e.day >= d - timedelta(days=days) and (levels is None or e.level in levels)
            )

        out: dict[str, object] = {f"min_{k}d": minutes(k) for k in (7, 14, 28, 56, 365)}
        out["min_intl_56d"] = minutes(56, ("international",))
        out["min_club_28d"] = minutes(28, CLUB_LEVELS)
        out["apps_20min_365d"] = sum(1 for e in year if e.minutes >= 20)  # noqa: PLR2004
        out["fge_30d"] = minutes(30) / FULL_MATCH
        out["season_minutes"] = sum(e.minutes for e in year if e.day >= season_start)
        for name, half_life in EWMA_HALF_LIVES.items():
            alpha = 1 - 0.5 ** (1 / half_life)
            out[name] = sum(
                e.minutes * alpha * 0.5 ** (((d - e.day).days - 1) / half_life) for e in year
            )
        return out

    def _sequence(self, past: list[Event], d: date, season_id: str) -> dict[str, object]:
        season = [e for e in past if e.season_id == season_id]

        def streak(cond: Any) -> int:
            n = 0
            for e in reversed(season):
                if not cond(e):
                    break
                n += 1
            return n

        played = [e for e in past if e.played]
        recent = [e for e in played if e.day >= d - timedelta(days=365)]
        days = (d - recent[-1].day).days if recent else NO_HISTORY
        short = 0
        for prev, cur in itertools.pairwise(played):
            if (
                cur.day >= d - timedelta(days=28)
                and (cur.day - prev.day).days < SHORT_TURNAROUND_DAYS
            ):
                short += 1
        weeks = {
            ((d - e.day).days - 1) // 7 + 1
            for e in past
            if e.on_sheet and d - timedelta(days=365) <= e.day < d
        }
        rest = 0
        while rest + 1 in weeks:
            rest += 1
        return {
            "consecutive_matches": streak(lambda e: e.played),
            "consecutive_starts": streak(lambda e: e.is_starter),
            "consecutive_heavy": streak(lambda e: e.minutes >= HEAVY_MINUTES),
            "days_since_last_match": days,
            "days_since_last_match_missing": not recent,
            "short_turnaround": days < SHORT_TURNAROUND_DAYS,
            "n_short_turnarounds_28d": short,
            "weeks_without_rest": rest,
        }

    def _international(
        self, past: list[Event], d: date, player_id: int, season_id: str
    ) -> dict[str, object]:
        tests = [
            e
            for e in past
            if e.played and e.level == "international" and d - timedelta(days=365) <= e.day < d
        ]
        active = [(start, r) for r, start, end in self.regimes if start <= d <= (end or date.max)]
        name = self.players[player_id][6]
        return {
            "intl_window": any(start <= d <= end for start, end in self.windows),
            "days_since_last_test": (d - tests[-1].day).days if tests else NO_HISTORY,
            "intl_caps_365d": len(tests),
            "protected_list": (season_id, name) in self.protected,
            "protection_regime": max(active)[1] if active else "none",
        }

    def _history(self, player_id: int, past: list[Event], d: date) -> dict[str, object]:
        known = [i for i in self.injuries[player_id] if i.onset < d]
        year = [i for i in known if i.onset >= d - timedelta(days=365)]
        returns = [i.return_date for i in known if i.return_date is not None and i.return_date < d]
        since_return = (d - max(returns)).days if returns else NO_HISTORY
        first = min([e.day for e in past] + [d])
        return {
            "n_prior_injuries_365d": len(year),
            "n_prior_injuries_career": len(known),
            "days_missed_365d": sum((min(i.return_date or d, d) - i.onset).days for i in year),
            "days_since_last_injury": (
                (d - max(i.onset for i in known)).days if known else NO_HISTORY
            ),
            "days_since_return": since_return,
            "recent_return_8w": since_return <= RECENT_RETURN_DAYS,
            "prior_concussions_365d": sum(1 for i in year if i.concussion),
            "observed_history_days": (d - first).days,
        }

    def _player(
        self, player_id: int, past: list[Event], d: date, season_id: str
    ) -> dict[str, object]:
        birth, h, w, pos, group, unit, _ = self.players[player_id]
        height = float(h) if h is not None else self._med(pos, "h")
        weight = float(w) if w is not None else self._med(pos, "w")
        bmi_med = self._med(pos, "bmi")
        bmi_rel = (
            weight / (height / 100) ** 2 - bmi_med
            if height is not None and weight is not None and bmi_med is not None
            else None
        )
        return {
            "age": (d - birth).days / 365.25 if birth is not None else None,
            "age_missing": birth is None,
            "height_cm": height,
            "height_missing": h is None,
            "weight_kg": weight,
            "weight_missing": w is None,
            "bmi_rel_position": bmi_rel,
            "pro_seasons": len({e.season_id for e in past if e.played and e.season_id < season_id}),
            "position_code": pos,
            "position_group": group,
            "unit": unit,
        }

    def _context(self, m: Match, team: int, as_of: datetime) -> dict[str, object]:
        opponent = m.away if team == m.home else m.home
        points = [
            _points(
                *(
                    (o.home_score, o.away_score)
                    if o.home == opponent
                    else (o.away_score, o.home_score)
                )
            )
            for o in self.matches.values()
            if opponent in (o.home, o.away)
            and o.competition_code == m.competition_code
            and o.season_id == m.season_id
            and o.kickoff < as_of
            and o.day < m.day
            and o.home_score is not None
            and o.away_score is not None
        ]
        team_matches = sorted(
            (o.kickoff, o.match_id)
            for o in self.matches.values()
            if team in (o.home, o.away) and o.season_id == m.season_id
        )
        period = next((p for limit, p in SEASON_PERIODS if m.day < limit), "from_2026_07")
        return {
            "is_home": team == m.home,
            "is_playoff": m.is_playoff,
            "month": m.day.month,
            "competition_code": m.competition_code,
            "season_round_index": team_matches.index((m.kickoff, m.match_id)) + 1,
            "surface": self.surface.get((m.venue_id, m.season_id), "unknown"),
            "season_period": period,
            "opponent_strength": sum(points) / len(points) if points else None,
            "opponent_strength_missing": not points,
        }
