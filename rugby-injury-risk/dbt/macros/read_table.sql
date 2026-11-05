{# Reads a warehouse table written outside dbt (Dagster assets); typed empty relation if absent. #}
{% macro read_table(table, columns) %}
{%- set n = 0 -%}
{%- if execute -%}
  {%- set n = run_query(
    "select count(*) from information_schema.tables where table_name = '" ~ table ~ "'"
  ).columns[0].values()[0] -%}
{%- endif -%}
{%- if n > 0 -%}
select {{ columns.keys() | join(', ') }} from {{ table }}
{%- else -%}
select
{%- for name, type in columns.items() %} null::{{ type }} as {{ name }}{{ "," if not loop.last }}
{%- endfor %}
where false
{%- endif -%}
{% endmacro %}
