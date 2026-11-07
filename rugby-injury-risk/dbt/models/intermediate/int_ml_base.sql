-- F17 : socle joueur × match d'équipe éligible (toutes compétitions), dates UTC.
-- `minutes` = minutes jouées (0 si non joué ; remplaçant sans minutes connues = non joué).
with base as (
  select
    e.player_id,
    e.match_id,
    e.team_id,
    m.season_id,
    m.competition_code,
    c.level,
    m.kickoff_ts,
    {{ utc_date('m.kickoff_ts') }} as match_date,
    e.on_sheet,
    coalesce(e.played, false) as played,
    coalesce(a.is_starter, false) as is_starter,
    case when coalesce(e.played, false) then coalesce(a.minutes_played, 0) else 0 end as minutes,
    a.minutes_played,
    m.venue_id,
    m.is_playoff,
    e.team_id = m.home_team_id as is_home,
    case when e.team_id = m.home_team_id then m.away_team_id else m.home_team_id end
      as opponent_id
  from {{ ref('fact_eligibility') }} e
  join {{ ref('fact_match') }} m using (match_id)
  join {{ ref('ref_competitions') }} c using (competition_code)
  left join {{ ref('fact_appearance') }} a using (match_id, player_id)
),
gaps as (
  -- Écart (jours) avec le match joué précédent, pour n_short_turnarounds_28d.
  select
    player_id, match_id,
    match_date - lag(match_date) over (partition by player_id order by kickoff_ts, match_id)
      as gap_days
  from base
  where played
)
select
  b.*,
  g.gap_days,
  -- Premier jour observé du joueur : min sur toutes ses lignes = min sur celles <= D.
  min(b.match_date) over (partition by b.player_id) as first_seen
from base b
left join gaps g using (player_id, match_id)
