-- Écrite par l'asset Dagster `player_entities` (F09).
{{ read_table('player_source_xref', {
  'source': 'varchar', 'source_player_id': 'varchar', 'player_id': 'bigint',
  'match_confidence': 'double', 'method': 'varchar'
}) }}
