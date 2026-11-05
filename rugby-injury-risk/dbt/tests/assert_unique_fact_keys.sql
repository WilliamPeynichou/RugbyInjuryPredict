-- Clés primaires composites (docs/04 §3) et clé naturelle de fact_match (§6).
select 'fact_appearance' as tbl, match_id::varchar as k from {{ ref('fact_appearance') }}
group by match_id, player_id having count(*) > 1
union all
select 'fact_eligibility', match_id::varchar from {{ ref('fact_eligibility') }}
group by match_id, player_id having count(*) > 1
union all
select 'fact_squad_membership', player_id::varchar from {{ ref('fact_squad_membership') }}
group by player_id, team_id, season_id, valid_from having count(*) > 1
union all
select 'fact_match', min(match_id)::varchar from {{ ref('fact_match') }}
group by competition_code, season_id, home_team_id, away_team_id, {{ utc_date('kickoff_ts') }}
having count(*) > 1
