"""Entity-resolution input records, built from staged matches, appearances and profiles."""

import polars as pl

from rugby_risk.entity_resolution.normalize import name_block, normalize_name
from rugby_risk.reference import team_canonical

NAME_SOURCE_PRIORITY = ("lnr", "allrugby", "worldrugby", "espn")
PROFILE_SOURCE_PRIORITY = ("allrugby", "espn", "worldrugby", "lnr")
CLUB_COMPETITIONS = ("TOP14", "PROD2", "CHAMPIONS_CUP", "CHALLENGE_CUP")


def _key(source: str, source_player_id: str) -> str:
    return f"{source}:{source_player_id}"


def build_records(
    matches: pl.DataFrame, appearances: pl.DataFrame, profiles: pl.DataFrame
) -> tuple[pl.DataFrame, pl.DataFrame, pl.DataFrame]:
    """Records + appearance rows + anchor input rows (match_key, match_date, team, shirt).

    Records: key, source, source_player_id, player_name (raw), name_norm, name_block,
    birth_date, birth_year, nationality, teams (list of "club|season"). Appearance rows carry
    match_date and match_key (match identity without match_id, so cross-source matches merge).
    """
    empty_records = pl.DataFrame(
        schema={
            "key": pl.String,
            "source": pl.String,
            "source_player_id": pl.String,
            "player_name": pl.String,
            "name_norm": pl.String,
            "name_block": pl.String,
            "birth_date": pl.Date,
            "birth_year": pl.Int64,
            "nationality": pl.String,
            "teams": pl.List(pl.String),
        }
    )
    empty_apps = pl.DataFrame(
        schema={"key": pl.String, "match_key": pl.String, "match_date": pl.Date}
    )
    empty_anchor = pl.DataFrame(
        schema={
            "key": pl.String,
            "source": pl.String,
            "match_key": pl.String,
            "match_date": pl.Date,
            "team": pl.String,
            "shirt_number": pl.Int64,
        }
    )
    if matches.is_empty() or appearances.is_empty():
        return empty_records, empty_apps, empty_anchor
    canonical = matches.with_columns(
        [
            pl.struct(["home_team_name", "source"])
            .map_elements(
                lambda m: team_canonical(m["home_team_name"], m["source"]) or m["home_team_name"],
                return_dtype=pl.String,
            )
            .alias("home_c"),
            pl.struct(["away_team_name", "source"])
            .map_elements(
                lambda m: team_canonical(m["away_team_name"], m["source"]) or m["away_team_name"],
                return_dtype=pl.String,
            )
            .alias("away_c"),
        ]
    ).select(
        "source_match_id",
        "competition_code",
        "season_id",
        pl.col("kickoff_ts").dt.date().alias("match_date"),
        pl.concat_str(
            [pl.col("home_c"), pl.col("away_c"), pl.col("kickoff_ts").dt.date().cast(pl.String)],
            separator="|",
        ).alias("match_key"),
    )
    app = appearances.join(canonical, on="source_match_id", how="left")
    apps = app.select(
        pl.struct(["source", "source_player_id"])
        .map_elements(lambda a: _key(a["source"], a["source_player_id"]), return_dtype=pl.String)
        .alias("key"),
        "match_key",
        "match_date",
    )
    anchor_apps = app.select(
        pl.struct(["source", "source_player_id"])
        .map_elements(lambda a: _key(a["source"], a["source_player_id"]), return_dtype=pl.String)
        .alias("key"),
        "source",
        "match_key",
        "match_date",
        pl.struct(["team_name", "source"])
        .map_elements(
            lambda t: team_canonical(t["team_name"], t["source"]) or t["team_name"],
            return_dtype=pl.String,
        )
        .alias("team"),
        pl.col("shirt_number").cast(pl.Int64, strict=False).alias("shirt_number"),
    )
    teams = (
        app.filter(pl.col("competition_code").is_in(CLUB_COMPETITIONS))
        .group_by(["source", "source_player_id"])
        .agg(
            pl.concat_str(
                [
                    pl.col("team_name").map_elements(
                        lambda n: team_canonical(n, "allrugby") or n, return_dtype=pl.String
                    ),
                    pl.lit("|"),
                    pl.col("season_id"),
                ]
            )
            .unique()
            .sort()
            .alias("teams")
        )
    )
    names = (
        app.group_by(["source", "source_player_id"])
        .agg(pl.col("player_name").first().alias("player_name"))
        .join(profiles, on=["source", "source_player_id"], how="left")
        .with_columns(
            [
                pl.col("player_name")
                .map_elements(normalize_name, return_dtype=pl.String)
                .alias("name_norm"),
                pl.col("birth_date").dt.year().cast(pl.Int64, strict=False).alias("birth_year"),
            ]
        )
        .with_columns(
            pl.col("name_norm").map_elements(name_block, return_dtype=pl.String).alias("name_block")
        )
    )
    records = (
        names.join(teams, on=["source", "source_player_id"], how="left")
        .with_columns(pl.col("teams").fill_null([]))
        .select(
            pl.struct(["source", "source_player_id"])
            .map_elements(
                lambda a: _key(a["source"], a["source_player_id"]), return_dtype=pl.String
            )
            .alias("key"),
            "source",
            "source_player_id",
            "player_name",
            "name_norm",
            "name_block",
            "birth_date",
            "birth_year",
            "nationality",
            "teams",
        )
    )
    return records, apps, anchor_apps


def pick_player_fields(
    records: pl.DataFrame, profiles: pl.DataFrame, xref: pl.DataFrame
) -> pl.DataFrame:
    joined = records.join(xref.select("key", "player_id"), on="key").join(
        profiles, on=["source", "source_player_id"], how="left"
    )
    players = []
    for group in joined.partition_by("player_id", maintain_order=False):
        row: dict[str, object] = {"player_id": int(group["player_id"][0])}
        ordered = group.sort(
            pl.col("source").map_elements(
                lambda src: (
                    NAME_SOURCE_PRIORITY.index(str(src))
                    if str(src) in NAME_SOURCE_PRIORITY
                    else len(NAME_SOURCE_PRIORITY)
                ),
                return_dtype=pl.Int64,
            )
        )
        row["full_name"] = ordered["player_name"].drop_nulls().first()
        for field in ("birth_date", "height_cm", "weight_kg", "nationality", "jiff"):
            values = group[field].drop_nulls()
            row[field] = values.first() if len(values) else None
        players.append(row)
    schema = {
        "player_id": pl.Int64,
        "full_name": pl.String,
        "birth_date": pl.Date,
        "height_cm": pl.Int64,
        "weight_kg": pl.Int64,
        "nationality": pl.String,
        "jiff": pl.Boolean,
    }
    return pl.DataFrame(players, schema=schema) if players else pl.DataFrame(schema=schema)
