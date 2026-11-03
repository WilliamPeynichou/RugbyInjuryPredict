{{ read_staging('appearance', {
  'source': 'varchar', 'source_match_id': 'varchar', 'source_player_id': 'varchar',
  'player_name': 'varchar', 'team_name': 'varchar', 'shirt_number': 'bigint', 'is_starter': 'boolean',
  'position_raw': 'varchar', 'minutes_played': 'bigint', 'yellow_cards': 'bigint', 'red_cards': 'bigint'
}) }}
