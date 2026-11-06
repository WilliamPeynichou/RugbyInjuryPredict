"""Link extracted mentions to players and matches (F15).

Player: exact normalised-name match (F09 `normalize_name`) restricted to the mention's team
and season (fact_squad_membership). 0 or >1 candidate -> player_id NULL + review queue.
Match: for onset in a match, the team's match closest before publication (<= 7 days).
"""

import csv
from datetime import date, timedelta
from pathlib import Path

import polars as pl

from rugby_risk.config.seasons import season_for_date
from rugby_risk.entity_resolution.normalize import normalize_name
from rugby_risk.reference import team_canonical

REVIEW_PATH = Path("data/review/news_player_queue.csv")
MATCH_LOOKUP_DAYS = 7


def _season_of(onset: date | None, fallback: date) -> str | None:
    return (season_for_date(onset) if onset else None) or season_for_date(fallback)


def link_players(
    mentions: pl.DataFrame,
    dim_player: pl.DataFrame,
    squad: pl.DataFrame,
    teams: pl.DataFrame,
    published: dict[str, date],
) -> pl.DataFrame:
    """Attach player_id (NULL when ambiguous) and set needs_review on doubt."""
    if mentions.is_empty():
        return mentions.with_columns(
            pl.lit(None, dtype=pl.Int64).alias("player_id"),
            pl.lit(True).alias("needs_review"),
        )
    players = dim_player.with_columns(
        pl.col("full_name").map_elements(normalize_name, return_dtype=pl.String).alias("norm")
    ).select("player_id", "norm", "full_name")
    squad_team = squad.join(teams.select("team_id", "name"), on="team_id")

    def resolve(row: dict[str, object]) -> tuple[int | None, bool]:
        name = str(row["player_name"] or "")
        norm = normalize_name(name)
        if not norm:
            return None, True
        season = _season_of(row["onset_date"], published[str(row["doc_id"])])  # type: ignore[arg-type]
        candidates = players.filter(pl.col("norm") == norm)
        if season is not None:
            team_raw = row["team_name"]
            club = team_canonical(str(team_raw), "*") if team_raw else None
            if club:
                team_ids = (
                    squad_team.filter((pl.col("season_id") == season) & (pl.col("name") == club))
                    .select("player_id")
                    .unique()
                )
                in_squad = candidates.join(team_ids, on="player_id")
                if not in_squad.is_empty():
                    candidates = in_squad
        if candidates.height == 1:
            return int(candidates.item(0, "player_id")), False
        return None, True

    resolved = [resolve(row) for row in mentions.to_dicts()]
    return mentions.with_columns(
        pl.Series("player_id", [p for p, _ in resolved], dtype=pl.Int64),
        pl.Series("needs_review", [r for _, r in resolved], dtype=pl.Boolean),
    )


def link_matches(
    mentions: pl.DataFrame,
    matches: pl.DataFrame,
    teams: pl.DataFrame,
    published: dict[str, date],
) -> pl.DataFrame:
    """For onset in a match: team match nearest before publication, <= 7 days."""
    if mentions.is_empty():
        return mentions.with_columns(pl.lit(None, dtype=pl.Int64).alias("match_id"))
    keys = (
        mentions.filter((pl.col("onset_context") == "match") & pl.col("player_id").is_not_null())
        .select("doc_id", "team_name")
        .unique()
        .to_dicts()
    )
    found: dict[tuple[str, str], int] = {}
    for row in keys:
        pub = published[str(row["doc_id"])]
        club = team_canonical(str(row["team_name"] or ""), "*")
        if club is None:
            continue
        team_ids = teams.filter(pl.col("name") == club).select("team_id").unique()
        if team_ids.is_empty():
            continue
        ids = set(team_ids["team_id"].to_list())
        candidates = matches.filter(
            pl.col("home_team_id").is_in(list(ids)) | pl.col("away_team_id").is_in(list(ids))
        ).with_columns(pl.col("kickoff_ts").dt.date().alias("d"))
        candidates = candidates.filter(
            (pl.col("d") <= pub) & (pl.col("d") >= pub - timedelta(days=MATCH_LOOKUP_DAYS))
        )
        if not candidates.is_empty():
            found[(str(row["doc_id"]), str(row["team_name"]))] = int(
                candidates.sort("kickoff_ts")[-1, "match_id"]
            )

    def match_id_for(row: dict[str, object]) -> int | None:
        if row["onset_context"] != "match" or row["player_id"] is None:
            return None
        return found.get((str(row["doc_id"]), str(row["team_name"] or "")))

    return mentions.with_columns(
        pl.Series(
            "match_id",
            [match_id_for(row) for row in mentions.to_dicts()],
            dtype=pl.Int64,
        )
    )


def write_review_queue(rows: list[dict[str, object]], path: Path = REVIEW_PATH) -> Path:
    """Ambiguous player mentions for human review (one row per unresolved mention)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    exists = path.exists()
    with path.open("a", newline="", encoding="utf-8") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["doc_id", "player_name", "team_name", "onset_date", "quote"],
            lineterminator="\n",
        )
        if not exists:
            writer.writeheader()
        for row in rows:
            writer.writerow({k: ("" if row.get(k) is None else row[k]) for k in writer.fieldnames})
    return path
