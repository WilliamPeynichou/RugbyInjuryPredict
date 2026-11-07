{{ read_staging('injury_episode', {
  'player_id': 'bigint', 'onset_date': 'date', 'onset_match_id': 'bigint',
  'context': 'varchar', 'body_region': 'varchar', 'injury_type': 'varchar',
  'is_concussion': 'boolean', 'return_date': 'date', 'days_missed': 'bigint',
  'severity_class': 'varchar', 'censored': 'boolean', 'source_confidence': 'double',
  'signals': 'varchar', 'evidence': 'varchar'
}) }}
