-- Une ligne par match source -> match_id (clé naturelle docs/04 §6, mêmes alias que le calendrier F08).
with src as (
  select
    source, source_match_id, competition_code, season_id, home_score, away_score,
    {{ canonical_team('home_team_name', 'source') }} as home_team_name,
    {{ canonical_team('away_team_name', 'source') }} as away_team_name,
    {{ utc_date('kickoff_ts') }} as match_date,
    {{ source_priority('source') }} as priority
  from {{ ref('stg_match') }}
)
select
  {{ stable_id("concat_ws('|', competition_code, season_id, home_team_name, away_team_name, match_date)") }}
    as match_id,
  *
from src
