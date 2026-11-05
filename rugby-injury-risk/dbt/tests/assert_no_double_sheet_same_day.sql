-- Aucun joueur sur deux feuilles de match le même jour.
select a.player_id, {{ utc_date('m.kickoff_ts') }} as match_date, count(*) as n
from {{ ref('fact_appearance') }} a join {{ ref('fact_match') }} m using (match_id)
group by 1, 2 having count(*) > 1
