{{ read_staging('fixture_calendar', {
  'competition_code': 'varchar', 'season_id': 'varchar', 'round': 'varchar',
  'kickoff_ts': 'timestamptz', 'kickoff_time_imputed': 'boolean', 'venue_name': 'varchar',
  'venue_id': 'bigint', 'home_team_name': 'varchar', 'away_team_name': 'varchar', 'source': 'varchar'
}) }}
