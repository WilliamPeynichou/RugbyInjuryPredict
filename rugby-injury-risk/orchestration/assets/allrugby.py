"""allrugby assets: raw page collection (live) then staging from the raw lake (offline)."""

from dagster import AssetExecutionContext, MaterializeResult, Output, asset

from orchestration.partitions import season_partitions
from rugby_risk.http import PoliteClient, RawStore
from rugby_risk.parsers.allrugby import MatchParseError, PlayerParseError, parse_match, parse_player
from rugby_risk.sources.allrugby.fetch import fetch_season
from rugby_risk.warehouse import staging_frame, write_staging


@asset(partitions_def=season_partitions, compute_kind="python")
async def allrugby_raw_pages(context: AssetExecutionContext) -> MaterializeResult:
    """Collect season/match/player pages into the raw lake. Live: requires human authorization."""
    season_id = context.partition_key
    known = {
        p.rsplit("-", 1)[-1].removesuffix(".html")
        for p in (
            row.url_canonical
            for row in RawStore().iter_manifest("allrugby")
            if "/joueurs/" in row.url_canonical
        )
    }
    async with PoliteClient("allrugby") as client:
        stats = await fetch_season(client, season_id, known_player_ids=known)
    return MaterializeResult(
        metadata={"match_pages": len(stats["match_ids"]), "player_pages": len(stats["player_ids"])}
    )


def _content(store: RawStore, url: str) -> str:
    result = store.get_latest("allrugby", url)
    if result is None:
        raise FileNotFoundError(url)
    return result.content.decode()


def _lake_rows(store: RawStore, url_filter: str) -> list:
    return [row for row in store.iter_manifest("allrugby") if url_filter in row.url_canonical]


def _write_matches(context: AssetExecutionContext) -> Output:
    store = RawStore()
    matches, appearances, quarantined = [], [], []
    for row in _lake_rows(store, "/matches/"):
        try:
            match, rows = parse_match(_content(store, row.url_canonical), context.partition_key)
        except MatchParseError as error:
            quarantined.append({"url": row.url_canonical, "reason": str(error)})
            continue
        matches.append(match)
        appearances.extend(rows)
    for entry in quarantined:
        context.log.warning("Quarantaine match: %s (%s)", entry["reason"], entry["url"])
    write_staging(staging_frame("match", matches), "match", "allrugby", context.partition_key)
    write_staging(
        staging_frame("appearance", appearances), "appearance", "allrugby", context.partition_key
    )
    return Output(None, metadata={"matches": len(matches), "quarantined": len(quarantined)})


@asset(partitions_def=season_partitions, compute_kind="python")
def allrugby_staging_matches(context: AssetExecutionContext) -> Output:
    """Parse raw match pages into staging Parquet (offline, idempotent: overwrite = stable)."""
    return _write_matches(context)


@asset(partitions_def=season_partitions, compute_kind="python")
def allrugby_staging_appearances(context: AssetExecutionContext) -> Output:
    """Same parse pass as matches, materialized for the appearance entity."""
    return _write_matches(context)


@asset(partitions_def=season_partitions, compute_kind="python")
def allrugby_staging_profiles(context: AssetExecutionContext) -> Output:
    """Parse raw player pages into staging Parquet."""
    store = RawStore()
    profiles, quarantined = [], []
    for row in _lake_rows(store, "/joueurs/"):
        try:
            player_id = row.url_canonical.rsplit("-", 1)[-1].removesuffix(".html")
            profiles.append(parse_player(_content(store, row.url_canonical), player_id))
        except PlayerParseError as error:
            quarantined.append({"url": row.url_canonical, "reason": str(error)})
    for entry in quarantined:
        context.log.warning("Quarantaine profil: %s (%s)", entry["reason"], entry["url"])
    write_staging(
        staging_frame("player_profile", profiles),
        "player_profile",
        "allrugby",
        context.partition_key,
    )
    return Output(None, metadata={"profiles": len(profiles), "quarantined": len(quarantined)})
