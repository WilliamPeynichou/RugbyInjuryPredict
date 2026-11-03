{# Reads data/staging/<entity>/**/*.parquet; typed empty relation when no file exists yet. #}
{% macro read_staging(entity, columns) %}
{%- set pattern = var('staging_dir', 'data/staging') ~ '/' ~ entity ~ '/**/*.parquet' -%}
{%- set n = 0 -%}
{%- if execute -%}
  {%- set n = run_query("select count(*) from glob('" ~ pattern ~ "')").columns[0].values()[0] -%}
{%- endif -%}
{%- if n > 0 -%}
select * from read_parquet('{{ pattern }}')
{%- else -%}
select
{%- for name, type in columns.items() %} null::{{ type }} as {{ name }}{{ "," if not loop.last }}
{%- endfor %}
where false
{%- endif -%}
{% endmacro %}
