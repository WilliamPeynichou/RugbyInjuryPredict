-- fact_eligibility enrichi : absence_reason rempli depuis int_absence_runs (F13).
-- fact_eligibility (sources) n'est jamais écrasé : l'enrichissement ne vit que dans ce modèle.
-- Même numérotation de séquences que int_absence_runs : une séquence démarre à chaque match
-- on_sheet (numéro courant = nombre de matchs on_sheet précédents, partition joueur x saison).
with ordered as (
  select
    e.match_id, e.player_id, m.season_id,
    sum(case when e.on_sheet then 1 else 0 end) over (
      partition by e.player_id, m.season_id order by m.kickoff_ts
      rows between unbounded preceding and current row
    ) as seq_id
  from {{ ref('fact_eligibility') }} e
  join {{ ref('fact_match') }} m using (match_id)
)
select
  e.match_id, e.player_id, e.team_id, e.on_sheet, e.played, r.absence_reason
from {{ ref('fact_eligibility') }} e
left join (
  select o.match_id, o.player_id, r.absence_reason
  from ordered o
  join {{ ref('int_absence_runs') }} r
    on r.player_id = o.player_id and r.season_id = o.season_id and r.seq_id = o.seq_id
) r using (match_id, player_id)
