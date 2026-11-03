{# Same HMAC as rugby_risk.privacy.player_key, registered as a DuckDB UDF by rugby_risk.dbt_plugin. #}
{% macro player_key(col) %}player_key({{ col }}){% endmacro %}
