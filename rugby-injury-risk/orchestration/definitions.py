from dagster import Definitions

from orchestration.assets.allrugby import (
    allrugby_raw_pages,
    allrugby_staging_appearances,
    allrugby_staging_matches,
    allrugby_staging_profiles,
)
from orchestration.assets.calendar import calendar_staging
from orchestration.assets.entities import (
    er_no_double_sheet_same_day,
    er_stable_ids,
    er_unique_source_id,
    player_entities,
)
from orchestration.assets.europe import europe_staging_espn
from orchestration.assets.internationals import (
    intl_minutes_check,
    intl_staging_espn,
    intl_staging_worldrugby,
)
from orchestration.assets.lnr import lnr_staging_lineups, lnr_vs_allrugby

defs = Definitions(
    assets=[
        allrugby_raw_pages,
        allrugby_staging_matches,
        allrugby_staging_appearances,
        allrugby_staging_profiles,
        lnr_staging_lineups,
        lnr_vs_allrugby,
        intl_staging_worldrugby,
        intl_staging_espn,
        intl_minutes_check,
        europe_staging_espn,
        calendar_staging,
        player_entities,
    ],
    asset_checks=[er_unique_source_id, er_no_double_sheet_same_day, er_stable_ids],
)
