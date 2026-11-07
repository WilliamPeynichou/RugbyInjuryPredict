"""F16: stratified sampling of episodes + non-episodes for human annotation.

`data/review/annotations.csv` is gitignored : décisions humaines, pas de code.
"""

import csv
import random
from dataclasses import dataclass
from pathlib import Path
from typing import Any

ANNOTATIONS_PATH = Path("data/review/annotations.csv")
BANDS = ((0.0, 0.6, "low"), (0.6, 0.9, "medium"), (0.9, 1.01, "high"))


@dataclass
class SampleItem:
    episode_kind: str  # episode | non_episode
    key: str  # player_id:onset_date[:body_region] ou player_id:match_id
    season: str
    band: str
    confidence: float
    summary: str


def _band(confidence: float) -> str:
    return next(name for lo, hi, name in BANDS if lo <= confidence < hi)


def _episode_rows(con: Any) -> list[dict[str, Any]]:
    episodes = con.execute(
        """select player_id, onset_date, body_region, context, source_confidence,
                  onset_match_id, signals
           from fact_injury_event order by player_id, onset_date"""
    ).fetchall()
    seasons = con.execute(
        """select e.player_id, e.onset_date, m.season_id
           from fact_injury_event e
           left join fact_match m on m.match_id = e.onset_match_id"""
    ).fetchall()
    season_of = {(p, d): s for p, d, s in seasons}
    rows = []
    for player_id, onset, region, context, conf, match_id, signals in episodes:
        season = season_of.get((player_id, onset)) or "unknown"
        key = f"{player_id}:{onset}:{region or ''}"
        summary = f"épisode {context} conf={conf:.2f} signaux={signals}"
        if match_id is not None:
            summary += f" match={match_id}"
        rows.append(
            dict(
                episode_kind="episode",
                key=key,
                season=str(season),
                confidence=float(conf),
                summary=summary,
            )
        )
    return rows


def _non_episode_rows(con: Any, n_per_band: int, rng: random.Random) -> list[dict[str, Any]]:
    """Appearances WITHOUT any injury signal : candidats not_injury pour le rappel."""
    rows = con.execute(
        """select a.player_id, a.match_id, m.season_id, m.match_date
           from fact_appearance a
           join fact_match m on m.match_id = a.match_id
           where not exists(
             select 1 from int_injury_signal__exit x
             where x.player_id = a.player_id and x.match_id = a.match_id)
           order by m.match_date"""
    ).fetchall()
    by_season: dict[str, list[tuple[int, int]]] = {}
    for player_id, match_id, season_id, _ in rows:
        by_season.setdefault(str(season_id), []).append((player_id, match_id))
    out = []
    for season, candidates in sorted(by_season.items()):
        rng.shuffle(candidates)
        for player_id, match_id in candidates[:n_per_band]:
            out.append(
                dict(
                    episode_kind="non_episode",
                    key=f"{player_id}:{match_id}",
                    season=season,
                    confidence=0.0,
                    summary="apparition sans signal",
                )
            )
    return out


def draw_sample(con: Any, n: int, seed: int) -> list[SampleItem]:
    """Stratified by confidence band (episodes) and season; plus non-episodes."""
    rng = random.Random(seed)
    episodes = _episode_rows(con)
    strata: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for row in episodes:
        key = (str(row["season"]), _band(float(row["confidence"])))
        strata.setdefault(key, []).append(row)
    per_stratum = max(1, n // max(1, len(strata)))
    picked: list[dict[str, Any]] = []
    for _key, pool in strata.items():
        stratum = pool.copy()
        rng.shuffle(stratum)
        picked.extend(stratum[:per_stratum])
    picked.extend(_non_episode_rows(con, n_per_band=max(1, n // 10), rng=rng))
    picked.sort(key=lambda r: (r["episode_kind"], r["season"], -r["confidence"]))
    return [
        SampleItem(
            episode_kind=r["episode_kind"],
            key=r["key"],
            season=r["season"],
            band=_band(r["confidence"]),
            confidence=float(r["confidence"]),
            summary=r["summary"],
        )
        for r in picked
    ]


def record_decision(key: str, episode_kind: str, decision: str, confidence: float) -> Path:
    ANNOTATIONS_PATH.parent.mkdir(parents=True, exist_ok=True)
    exists = ANNOTATIONS_PATH.exists()
    with ANNOTATIONS_PATH.open("a", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        if not exists:
            writer.writerow(["key", "episode_kind", "source_confidence", "decision"])
        writer.writerow([key, episode_kind, f"{confidence:.4f}", decision])
    return ANNOTATIONS_PATH
