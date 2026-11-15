-- Joueur × match de son équipe, joué ou non : effectif (club × période) × matchs du club,
-- plus toute feuille de match (sélections internationales incluses).
with squad_matches as (
  select m.match_id, s.player_id, s.team_id
  from {{ ref('fact_squad_membership') }} s
  join {{ ref('fact_match') }} m
    on m.season_id = s.season_id
    and s.team_id in (m.home_team_id, m.away_team_id)
    and {{ utc_date('m.kickoff_ts') }} between s.valid_from and s.valid_to
),
candidates as (
  select match_id, player_id, team_id, 1 as priority from {{ ref('fact_appearance') }}
  union all
  select match_id, player_id, team_id, 2 from squad_matches
)
select
  c.match_id,
  c.player_id,
  c.team_id,
  a.player_id is not null as on_sheet,
  -- NULL = remplaçant sur la feuille dont aucune source ne donne les minutes.
  case
    when a.player_id is null then false
    when a.minutes_played is not null then a.minutes_played > 0
    when a.is_starter then true
  end as played,
  null::varchar as absence_reason
from candidates c
left join {{ ref('fact_appearance') }} a using (match_id, player_id)
qualify row_number() over (partition by c.match_id, c.player_id order by c.priority) = 1
