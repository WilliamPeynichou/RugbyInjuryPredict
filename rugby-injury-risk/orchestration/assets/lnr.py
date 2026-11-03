"""Assets LNR : compositions officielles (offline depuis le lac) + diff allrugby."""

import re
import unicodedata

import polars as pl
from dagster import (
    AssetExecutionContext,
    MultiPartitionsDefinition,
    Output,
    StaticPartitionsDefinition,
    asset,
)

from orchestration.assets.allrugby import _content
from orchestration.partitions import season_partitions
from rugby_risk.http import RawStore
from rugby_risk.parsers.lnr import LineupParseError, parse_lineup
from rugby_risk.settings import get_settings
from rugby_risk.warehouse import staging_frame, write_staging

round_partitions = StaticPartitionsDefinition(
    [*(f"J{i}" for i in range(1, 27)), "Barrage", "Demi", "Finale"]
)
season_round_partitions = MultiPartitionsDefinition(
    {"season": season_partitions, "round": round_partitions}
)


def _season_round(context: AssetExecutionContext) -> tuple[str, str]:
    keys = context.partition_key.keys_by_dimension
    return keys["season"], keys["round"]


def _profiles_from_lineups(appearances: list[dict[str, object]]) -> list[dict[str, object]]:
    seen: dict[str, dict[str, object]] = {}
    for row in appearances:
        seen.setdefault(
            str(row["source_player_id"]),
            {
                "source": "lnr",
                "source_player_id": row["source_player_id"],
                "full_name": row["player_name"],
                "birth_date": None,
                "height_cm": None,
                "weight_kg": None,
                "nationality": None,
                "jiff": None,
                "positions_raw": row["position_raw"],
            },
        )
    return list(seen.values())


@asset(partitions_def=season_round_partitions, compute_kind="python")
def lnr_staging_lineups(context: AssetExecutionContext) -> Output:
    """Parse les feuilles LNR du lac brut pour (saison, journée) → staging."""
    season_id, round_id = _season_round(context)
    store = RawStore()
    prefix = f"/feuille-de-match/{season_id}/{round_id.lower()}/"
    matches, appearances, profiles, quarantined = [], [], [], []
    manifest_rows = [r for r in store.iter_manifest("lnr") if prefix in r.url_canonical]
    for row in manifest_rows:
        try:
            match, lineup_rows = parse_lineup(_content(store, row.url_canonical, "lnr"), season_id)
        except LineupParseError as error:
            quarantined.append({"url": row.url_canonical, "reason": str(error)})
            continue
        matches.append(match)
        appearances.extend(lineup_rows)
        profiles.extend(_profiles_from_lineups(lineup_rows))
    for entry in quarantined:
        context.log.warning("Quarantaine LNR: %s (%s)", entry["reason"], entry["url"])
    write_staging(staging_frame("match", matches), "match", "lnr", season_id)
    write_staging(staging_frame("appearance", appearances), "appearance", "lnr", season_id)
    write_staging(staging_frame("player_profile", profiles), "player_profile", "lnr", season_id)
    return Output(
        None,
        metadata={
            "matches": len(matches),
            "quarantined": len(quarantined),
            "profiles": len(profiles),
        },
    )


def _norm_name(name: str) -> str:
    folded = unicodedata.normalize("NFKD", name).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z]", "", folded.lower())


@asset(partitions_def=season_partitions, compute_kind="python")
def lnr_vs_allrugby(context: AssetExecutionContext) -> Output:
    """Rapport de cohérence : joueurs présents dans une seule des deux sources, par match."""
    season_id = context.partition_key
    staging = get_settings().data_dir / "staging"
    frames = {}
    for source in ("lnr", "allrugby"):
        path = staging / "appearance" / f"source={source}" / f"season={season_id}" / "part.parquet"
        frames[source] = pl.read_parquet(path) if path.exists() else None
    if frames["lnr"] is None or frames["allrugby"] is None:
        return Output(None, metadata={"diff_rows": 0, "note": "source manquante"})
    lnr, allrugby = frames["lnr"], frames["allrugby"]
    matches_lnr = lnr.select(
        ["source_match_id", "team_name", "player_name", "shirt_number"]
    ).unique()
    matches_ar = allrugby.select(
        ["source_match_id", "team_name", "player_name", "shirt_number"]
    ).unique()
    lnr_keys = matches_lnr.with_columns(
        pl.concat_str(
            [
                pl.col("team_name"),
                pl.col("player_name").map_elements(_norm_name, return_dtype=pl.String),
                pl.col("shirt_number").cast(pl.String),
            ]
        ).alias("key")
    )
    ar_keys = matches_ar.with_columns(
        pl.concat_str(
            [
                pl.col("team_name"),
                pl.col("player_name").map_elements(_norm_name, return_dtype=pl.String),
                pl.col("shirt_number").cast(pl.String),
            ]
        ).alias("key")
    )
    only_lnr = lnr_keys.join(ar_keys.select("key"), on="key", how="anti")
    only_ar = ar_keys.join(lnr_keys.select("key"), on="key", how="anti")
    report = pl.concat(
        [
            only_lnr.with_columns(pl.lit("lnr_only").alias("status")),
            only_ar.with_columns(pl.lit("allrugby_only").alias("status")),
        ]
    ).with_columns(pl.lit(season_id).alias("season_id"))
    out_dir = staging / "_reports" / "lineup_diff"
    out_dir.mkdir(parents=True, exist_ok=True)
    report.write_parquet(out_dir / f"season={season_id}.parquet", compression="zstd")
    return Output(None, metadata={"diff_rows": report.height})
