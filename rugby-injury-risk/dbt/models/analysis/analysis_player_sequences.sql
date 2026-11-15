-- Une ligne par séquence de matchs consécutifs joués (≥ 1 minute) d'un joueur, par saison.
-- Raison de fin : match d'équipe suivant manqué (absence), sur la feuille sans jouer
-- (bench_unused), ou plus aucun match d'équipe dans la saison (end_of_season).
with elig as (
  select
    e.player_id, e.on_sheet, m.season_id, m.kickoff_ts, m.competition_code,
    -- remplaçant sans minutes connues (played NULL) : compté comme non joué.
    coalesce(e.played, false) as played,
    a.minutes_played, a.position_played
  from {{ ref('fact_eligibility') }} e
  join {{ ref('fact_match') }} m using (match_id)
  left join {{ ref('fact_appearance') }} a using (match_id, player_id)
),
runs as (
  select
    *,
    {{ consecutive_run_id('player_id, season_id', 'kickoff_ts', 'played') }} as run_id,
    lead(on_sheet) over w as next_on_sheet,
    lead(kickoff_ts) over w is not null as has_next
  from elig
  window w as (partition by player_id, season_id order by kickoff_ts)
),
seqs as (
  select
    player_id, season_id, run_id,
    min(kickoff_ts) as start_ts,
    max(kickoff_ts) as end_ts,
    count(*) as length,
    sum(minutes_played) as total_minutes,
    string_agg(distinct competition_code, ',' order by competition_code) as competitions,
    mode(position_played) as position_mode,
    arg_max(has_next, kickoff_ts) as has_next,
    arg_max(next_on_sheet, kickoff_ts) as next_on_sheet
  from runs
  where played
  group by player_id, season_id, run_id
)
select
  s.player_id,
  s.season_id,
  coalesce(d.primary_position, s.position_mode) as position_code,
  s.start_ts,
  s.end_ts,
  s.length,
  s.total_minutes,
  s.competitions,
  case when not s.has_next then 'end_of_season' when s.next_on_sheet then 'bench_unused'
    else 'absence' end as end_reason
from seqs s
left join {{ ref('dim_player') }} d using (player_id)
