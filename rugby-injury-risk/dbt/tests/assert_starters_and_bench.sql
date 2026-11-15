-- 15 titulaires et au plus 8 remplaçants par équipe et par match (warn : feuilles partielles).
{{ config(severity='warn') }}
select match_id, team_id, count(*) filter (where is_starter) as starters,
  count(*) filter (where not is_starter) as bench
from {{ ref('fact_appearance') }}
group by match_id, team_id
having count(*) filter (where is_starter) <> 15 or count(*) filter (where not is_starter) > 8
