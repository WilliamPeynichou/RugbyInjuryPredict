{{ read_staging('player_profile', {
  'source': 'varchar', 'source_player_id': 'varchar', 'full_name': 'varchar', 'birth_date': 'date',
  'height_cm': 'bigint', 'weight_kg': 'bigint', 'nationality': 'varchar', 'jiff': 'boolean',
  'positions_raw': 'varchar'
}) }}
