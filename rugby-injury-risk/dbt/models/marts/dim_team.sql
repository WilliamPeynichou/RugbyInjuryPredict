-- Équipes canoniques : alias de référence + noms vus au calendrier (alias manquant = nom brut).
-- team_id = md5 du nom canonique (stable entre deux runs ; collision vérifiée par le test unique).
with seen as (
  select home_team_name as name, competition_code from {{ ref('stg_fixture_calendar') }}
  union all
  select away_team_name, competition_code from {{ ref('stg_fixture_calendar') }}
  union all
  select team_canonical, null from {{ ref('ref_team_aliases') }}
),
teams as (
  select s.name, bool_or(c.level = 'international') as plays_tests
  from seen s left join {{ ref('ref_competitions') }} c using (competition_code)
  group by s.name
),
alias as (
  select team_canonical as name, bool_or(is_national) as is_national, min(country) as country
  from {{ ref('ref_team_aliases') }} group by team_canonical
)
select
  {{ stable_id('t.name', 7) }}::integer as team_id,
  t.name,
  null::varchar as short_name,
  a.country,
  coalesce(a.is_national, t.plays_tests, false) as is_national
from teams t left join alias a using (name)
