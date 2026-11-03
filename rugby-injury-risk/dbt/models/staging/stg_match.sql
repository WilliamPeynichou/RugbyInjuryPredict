{{ read_staging('match', {
  'source': 'varchar', 'source_match_id': 'varchar', 'competition_code': 'varchar',
  'season_id': 'varchar', 'round': 'varchar', 'kickoff_ts': 'timestamptz', 'venue_name': 'varchar',
  'home_team_name': 'varchar', 'away_team_name': 'varchar', 'home_score': 'bigint', 'away_score': 'bigint'
}) }}
