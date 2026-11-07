-- F17 docs/05 §6 : contexte du match t, connu avant le coup d'envoi.
-- opponent_strength = points/match de l'adversaire dans la compétition et la saison, matchs < D.
-- shortcut: barème 4/2/0 + bonus défensif (écart <= 5) ; bonus offensif absent (essais inconnus).
with team_match as (
  select match_id, season_id, competition_code, kickoff_ts, {{ utc_date('kickoff_ts') }} as d,
    home_team_id as team_id, home_score as pf, away_score as pa
  from {{ ref('fact_match') }}
  union all
  select match_id, season_id, competition_code, kickoff_ts, {{ utc_date('kickoff_ts') }},
    away_team_id, away_score, home_score
  from {{ ref('fact_match') }}
),
ranked as (
  select
    *,
    row_number() over (partition by team_id, season_id order by kickoff_ts, match_id)
      as season_round_index,
    case when pf is null or pa is null then null when pf > pa then 4 when pf = pa then 2 when pa - pf <= 5 then 1 else 0 end as pts
  from team_match
),
strength as (
  select b.player_id, b.match_id, avg(o.pts) as opponent_strength
  from {{ ref('int_ml_base') }} b
  join ranked o
    on o.team_id = b.opponent_id
    and o.competition_code = b.competition_code
    and o.season_id = b.season_id
    and o.d < b.match_date
    and o.pts is not null
  group by b.player_id, b.match_id
)
select
  b.player_id,
  b.match_id,
  b.competition_code,
  b.is_home,
  b.is_playoff,
  month(b.match_date)::integer as month,
  r.season_round_index::integer as season_round_index,
  coalesce(vs.surface, 'unknown') as surface,
  case
    when b.match_date < date '2017-07-01' then 'pre_2017'
    when b.match_date < date '2018-07-01' then '2017_2018'
    when b.match_date < date '2026-07-01' then '2018_2026'
    else 'from_2026_07'
  end as season_period,
  s.opponent_strength,
  s.opponent_strength is null as opponent_strength_missing
from {{ ref('int_ml_base') }} b
join ranked r on r.match_id = b.match_id and r.team_id = b.team_id
left join strength s on s.player_id = b.player_id and s.match_id = b.match_id
left join {{ ref('ref_venue_surface') }} vs
  on vs.venue_id = b.venue_id and vs.season_id = b.season_id
