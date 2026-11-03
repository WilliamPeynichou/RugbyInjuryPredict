# F12 — Signal « sortie précoce »

| Champ | Valeur |
|---|---|
| Phase | 3 |
| Dépendances | F10 |
| Estimation | M |
| Docs de référence | `docs/01-data-sources.md` §4, `docs/04-data-model.md` (`fact_appearance.off_reason`) |

## Objectif

Identifier les sorties de match candidates à une blessure à partir des minutes et du statut titulaire/remplaçant, avec un score de suspicion.

## Contexte

Premier des trois signaux de labellisation. Il est bruité (remplacements tactiques précoces, pack remplacé en bloc à la 50e) et doit être croisé avec les annonces (F15) et les absences (F13) dans F16.

## Périmètre

- [ ] Modèle dbt `int_injury_signal__exit` : une ligne par apparition candidate avec `signal_strength ∈ [0, 1]`.
- [ ] Règles de base (paramètres dans `config/injury_rules.yaml`, créé ici) :
  - titulaire sorti avant la minute `T_early(position_group)` : seuils par défaut 40 (front_row), 45 (lock, back_row), 55 (dos) — les avants sont remplacés tôt pour raisons tactiques ;
  - remplaçant entré puis ressorti avant la fin (hors carton) : force 0,9 ;
  - sortie dans les 20 premières minutes : force 0,8 quel que soit le poste ;
  - modulation : si plusieurs joueurs de la même ligne sortent à la même minute → remplacement en bloc, force × 0,3 ;
  - si le joueur est absent au match suivant de son équipe → force + 0,2 (plafonnée à 1).
- [ ] Mise à jour de `off_reason` en `injury_suspected` lorsque `signal_strength ≥ 0.7` (colonne dérivée dans un modèle intermédiaire, pas d'écrasement des sources).
- [ ] Rapport de calibrage des seuils : distribution des minutes de sortie par poste (permet à l'humain d'ajuster `injury_rules.yaml`).

## Hors périmètre

- Texte des comptes rendus (F15). Décision finale « blessure » (F16).

## Spécification technique

```yaml
# config/injury_rules.yaml
exit_signal:
  early_exit_minute: { front_row: 40, lock: 45, back_row: 45, half_back: 55, centre: 55, back_three: 55 }
  very_early_minute: 20
  sub_off_strength: 0.9
  very_early_strength: 0.8
  block_change_factor: 0.3
  absent_next_bonus: 0.2
  suspected_threshold: 0.7
```

Le signal « absent au match suivant » utilise une information **postérieure** au match : c'est autorisé pour la **labellisation** (cible), jamais pour les features. Le commentaire doit le dire explicitement dans le SQL.

## Fichiers

| Fichier | Action |
|---|---|
| `config/injury_rules.yaml` | créer |
| `dbt/models/intermediate/int_injury_signal__exit.sql` + `.yml` | créer |
| `src/rugby_risk/injuries/{__init__,rules}.py` (chargement de la config, exposée à dbt via vars) | créer |

## Tests

- `tests/integration/injuries/test_exit_signal.py` — cas synthétiques : titulaire pilier sorti 50e (pas de signal), ailier sorti 25e (signal), remplaçant entré 55e sorti 70e (signal fort), trois avants sortis à la 52e (bloc, signal faible), joueur sorti 30e absent le match suivant (signal renforcé).

## Critères d'acceptation

- [ ] Les 5 cas synthétiques donnent la force attendue (± 0,01).
- [ ] Les seuils sont uniquement dans `config/injury_rules.yaml`.
- [ ] `make check` vert.

## Journal

