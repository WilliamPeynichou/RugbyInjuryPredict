-- F16 : épisodes de blessure candidats, fusion des signaux sortie/absence/annonce.
-- Grain docs/04 §3 : (player_id, onset_date, body_region). Confiance : config/injury_rules.yaml.
select
  {{ stable_id("concat_ws('|', player_id, onset_date, coalesce(body_region, ''))") }}
    as injury_id,
  player_id,
  onset_date,
  onset_match_id,
  context,
  body_region,
  injury_type,
  is_concussion,
  return_date,
  days_missed,
  severity_class,
  censored,
  source_confidence,
  string_split(signals, '|') as signals,
  evidence::json as evidence
from {{ ref('stg_injury_episode') }}
