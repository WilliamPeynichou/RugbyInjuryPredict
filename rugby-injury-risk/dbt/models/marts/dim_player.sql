-- dim_player est produite par l'asset Dagster `player_entities` (table `er_dim_player`,
-- chargée depuis tous les staging). Tant que la résolution n'a pas tourné, la table est
-- absente : on expose alors une relation vide typée (même convention que read_staging).
{{ config(materialized='table') }}
{% set columns = {
  'player_id': 'bigint', 'player_key': 'varchar', 'full_name': 'varchar',
  'birth_date': 'date', 'height_cm': 'bigint', 'weight_kg': 'bigint',
  'nationality': 'varchar', 'jiff': 'boolean', 'primary_position': 'varchar',
  'position_group': 'varchar', 'unit': 'varchar'
} %}
{% if execute %}
  {% set n = run_query(
    "select count(*) from information_schema.tables where table_name = 'er_dim_player'"
  ).columns[0].values()[0] %}
{% endif %}
{% if execute and n > 0 %}
select * from er_dim_player
{% else %}
select
{%- for name, type in columns.items() %} null::{{ type }} as {{ name }}{{ "," if not loop.last }}
{%- endfor %}
where false
{% endif %}
