from dagster import Definitions

from orchestration.assets.allrugby import (
    allrugby_raw_pages,
    allrugby_staging_appearances,
    allrugby_staging_matches,
    allrugby_staging_profiles,
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
    ]
)
