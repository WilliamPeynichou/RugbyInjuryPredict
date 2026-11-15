-- dim_player est produite par l'asset Dagster `player_entities` (table `er_dim_player`).
-- Tant que la résolution n'a pas tourné, relation vide typée (convention read_staging).
{{ read_table('er_dim_player', {
  'player_id': 'bigint', 'player_key': 'varchar', 'full_name': 'varchar',
  'birth_date': 'date', 'height_cm': 'bigint', 'weight_kg': 'bigint',
  'nationality': 'varchar', 'jiff': 'boolean', 'primary_position': 'varchar',
  'position_group': 'varchar', 'unit': 'varchar'
}) }}
