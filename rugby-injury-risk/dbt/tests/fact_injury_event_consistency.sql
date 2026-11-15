-- F16 : cohérence interne de fact_injury_event (pas de dbt_utils : tests singuliers).
select injury_id
from {{ ref('fact_injury_event') }}
where return_date < onset_date
   or days_missed < 0
   or source_confidence < 0
   or source_confidence > 1
   or (return_date is not null and days_missed is null)
