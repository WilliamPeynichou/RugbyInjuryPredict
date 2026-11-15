-- Périodes d'indisponibilité non-blessure (F13) : une ligne par run d'absence classé,
-- hors injury_candidate. Grain docs/04 §3 (player, start_date, end_date).
select
  player_id,
  start_date,
  end_date,
  absence_reason as reason,
  censored_end_of_season,
  n_matches as matches_missed
from {{ ref('int_absence_runs') }}
where absence_reason <> 'injury_candidate'
