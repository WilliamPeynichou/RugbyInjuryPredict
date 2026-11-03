from dagster import StaticPartitionsDefinition

from rugby_risk.config.seasons import load_seasons

season_partitions = StaticPartitionsDefinition([s.season_id for s in load_seasons()])
