{# Single implementation of match sequences (docs/05 §2 consecutive_matches; reused by F17).
   Over a player's ordered team matches, the run id increments on every match where
   `condition` is false: rows sharing a run id with `condition` true form one sequence. #}
{% macro consecutive_run_id(partition_by, order_by, condition) -%}
sum(case when {{ condition }} then 0 else 1 end) over (
  partition by {{ partition_by }} order by {{ order_by }}
  rows between unbounded preceding and current row
)
{%- endmacro %}
