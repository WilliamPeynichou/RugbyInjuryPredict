from dagster import Definitions

from orchestration.assets.allrugby import (
    allrugby_raw_pages,
    allrugby_staging_appearances,
    allrugby_staging_matches,
    allrugby_staging_profiles,
)

defs = Definitions(
    assets=[
        allrugby_raw_pages,
        allrugby_staging_matches,
        allrugby_staging_appearances,
        allrugby_staging_profiles,
    ]
)
