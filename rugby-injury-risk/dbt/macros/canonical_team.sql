{# Same lookup as rugby_risk.reference.team_canonical: source alias, then '*' alias, else raw name. #}
{% macro canonical_team(col, source_col) %}coalesce(
  (select min(a.team_canonical) from {{ ref('ref_team_aliases') }} a
   where a.raw_name = {{ col }} and a.source = {{ source_col }}),
  (select min(a.team_canonical) from {{ ref('ref_team_aliases') }} a
   where a.raw_name = {{ col }} and a.source = '*'),
  {{ col }})
{%- endmacro %}

{# Composition priority shared with rugby_risk.calendar.PRIORITY. #}
{% macro source_priority(col) %}case {{ col }}
  when 'lnr' then 0 when 'allrugby' then 1 when 'worldrugby' then 2
  when 'espn' then 3 when 'espn_europe' then 3 when 'apisports' then 4 else 5 end
{%- endmacro %}

{# UTC calendar date of a timestamptz (DuckDB casts use the session time zone otherwise). #}
{% macro utc_date(col) %}(({{ col }}) at time zone 'UTC')::date{% endmacro %}
