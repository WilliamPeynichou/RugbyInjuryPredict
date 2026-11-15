-- Somme des minutes par équipe ∈ [1100, 1300] (warn : seuil bloquant = asset check 98 %/saison).
{{ config(severity='warn') }}
select match_id, team_id, sum(minutes_played) as minutes
from {{ ref('fact_appearance') }}
group by match_id, team_id
having sum(minutes_played) is not null and sum(minutes_played) not between 1100 and 1300
