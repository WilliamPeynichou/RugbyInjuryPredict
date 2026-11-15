select * from {{ ref('fact_appearance') }} where minutes_played not between 0 and 100
