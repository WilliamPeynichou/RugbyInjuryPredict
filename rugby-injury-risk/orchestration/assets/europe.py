"""European cups assets: Champions Cup / Challenge Cup games of Top 14 clubs (ESPN, offline)."""

from dagster import AssetExecutionContext, Output, asset

from orchestration.assets.allrugby import _content
from orchestration.assets.internationals import _write
from orchestration.partitions import season_partitions
from rugby_risk.http import RawStore
from rugby_risk.parsers.espn import parse_europe
from rugby_risk.parsers.intl import IntlParseError


@asset(partitions_def=season_partitions, compute_kind="python")
def europe_staging_espn(context: AssetExecutionContext) -> Output:
    """Parse ESPN European cup summaries from the raw lake into staging (source=espn_europe)."""
    store = RawStore()
    parsed, quarantined = [], []
    for row in store.iter_manifest("espn"):
        if "/summary?" not in row.url_canonical:
            continue
        try:
            result = parse_europe(_content(store, row.url_canonical, "espn"))
        except IntlParseError as error:
            quarantined.append({"url": row.url_canonical, "reason": str(error)})
            continue
        if result is not None:
            parsed.append(result)
    # Chemin distinct de intl_staging_espn (même source ESPN, sinon écrasement du part.parquet).
    return _write(context, "espn_europe", parsed, quarantined)
