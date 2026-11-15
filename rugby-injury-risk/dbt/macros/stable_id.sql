{# Deterministic id from a natural key: first `digits` hex chars of md5 (15 -> BIGINT, 7 -> INTEGER). #}
{% macro stable_id(expr, digits=15) %}('0x' || substr(md5({{ expr }}), 1, {{ digits }}))::bigint{% endmacro %}
