-- Répartition des motifs d'absence par saison et poste (F13, rapport). Grains agrégés.
select
  r.season_id,
  coalesce(r.position_code, 'UNK') as position_code,
  r.absence_reason,
  count(*) as n_players,
  sum(r.n_matches) as matches_missed
from {{ ref('int_absence_runs') }} r
group by r.season_id, coalesce(r.position_code, 'UNK'), r.absence_reason
