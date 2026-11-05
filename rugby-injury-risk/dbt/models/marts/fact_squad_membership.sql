-- Appartenance club × saison déduite des apparitions en championnat (club_domestic) :
-- [première, dernière] apparition, élargie au début de saison pour le premier club du joueur
-- et à la fin de saison pour le dernier (un transfert en cours de saison n'est donc pas élargi).
with apps as (
  select a.player_id, a.team_id, m.season_id, {{ utc_date('m.kickoff_ts') }} as match_date
  from {{ ref('fact_appearance') }} a
  join {{ ref('fact_match') }} m using (match_id)
  join {{ ref('dim_team') }} t on t.team_id = a.team_id
  join {{ ref('ref_competitions') }} c on c.competition_code = m.competition_code
  where not t.is_national and c.level = 'club_domestic'
),
spans as (
  select player_id, team_id, season_id, min(match_date) as first_app, max(match_date) as last_app
  from apps group by player_id, team_id, season_id
),
ranked as (
  select
    *,
    first_app = min(first_app) over w as is_first_club,
    last_app = max(last_app) over w as is_last_club
  from spans
  window w as (partition by player_id, season_id)
)
select
  r.player_id,
  r.team_id,
  r.season_id,
  case when r.is_first_club then s.start_date else r.first_app end as valid_from,
  case when r.is_last_club then s.end_date else r.last_app end as valid_to
from ranked r join {{ ref('ref_seasons') }} s using (season_id)
