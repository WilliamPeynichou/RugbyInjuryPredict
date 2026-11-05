-- Contrôle des minutes par match : somme par équipe ∈ [1100, 1300] pour les deux équipes.
with team_minutes as (
  select match_id, team_id, sum(minutes_played) as minutes
  from {{ ref('fact_appearance') }} group by match_id, team_id
)
select
  m.match_id,
  m.season_id,
  m.competition_code,
  h.minutes is not null or a.minutes is not null as has_minutes,
  coalesce(h.minutes between 1100 and 1300 and a.minutes between 1100 and 1300, false) as minutes_ok
from {{ ref('fact_match') }} m
left join team_minutes h on h.match_id = m.match_id and h.team_id = m.home_team_id
left join team_minutes a on a.match_id = m.match_id and a.team_id = m.away_team_id
