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

- [x] Modèle dbt `int_injury_signal__exit` : une ligne par apparition candidate avec `signal_strength ∈ [0, 1]`.
- [x] Règles de base (paramètres dans `config/injury_rules.yaml`, créé ici) :
  - titulaire sorti avant la minute `T_early(position_group)` : seuils par défaut 40 (front_row), 45 (lock, back_row), 55 (dos) — les avants sont remplacés tôt pour raisons tactiques ;
  - remplaçant entré puis ressorti avant la fin (hors carton) : force 0,9 ;
  - sortie dans les 20 premières minutes : force 0,8 quel que soit le poste ;
  - modulation : si plusieurs joueurs de la même ligne sortent à la même minute → remplacement en bloc, force × 0,3 ;
  - si le joueur est absent au match suivant de son équipe → force + 0,2 (plafonnée à 1).
- [x] Mise à jour de `off_reason` en `injury_suspected` lorsque `signal_strength ≥ 0.7` (colonne dérivée dans un modèle intermédiaire, pas d'écrasement des sources).
- [x] Rapport de calibrage des seuils : distribution des minutes de sortie par poste (permet à l'humain d'ajuster `injury_rules.yaml`).

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

- [x] Les 5 cas synthétiques donnent la force attendue (± 0,01).
- [x] Les seuils sont uniquement dans `config/injury_rules.yaml`.
- [x] `make check` vert.

## Journal

- 2026-11-05 — Livré sur branche `feat/F12-signal-exits`.
  - Seuils **uniquement** dans `config/injury_rules.yaml`, validés Pydantic (`rules.py`),
    passés à dbt comme vars (`make dbt` et `build_marts` via
    `python -m rugby_risk.injuries.rules`).
  - Force d'un sortie « précoce » titulaire = `early_exit_strength` (0,7), absent de la
    spécification de la fiche ; ajouté à la config (même style que `sub_off_strength`).
  - **Cas « trois avants à la 52e »** : à la 52e aucun groupe de poste n'a de seuil
    « précoce » atteint (avants : 40/45), donc force de base nulle et pas de ligne de signal
    (règle = sortie *précoce*). Le facteur « bloc » × 0,3 est exercé par trois 3es lignes à
    la 42e (0,21). Détail enregistré ici, cas testé conforme à la spéc.
  - Sortie d'un remplaçant (`minute_off` non nul, hors carton) : signal `sub_off_strength`
    (0,9). Ne peut pas se produire aujourd'hui : aucun source ne donne `minute_off` d'un
    remplaçant (docs/01 §4) ; la règle existe pour Sportradar/annotation (F15, F16).
  - `off_reason` = colonne dérivée `off_reason_derived` (les sources ne sont jamais écrasées).
  - Test d'intégration sur tables marts synthétiques (`select` unique du modèle dbt) ; aucun
    poids de remplacement global : `ref_positions` est le seul objet compilé par dbt.
  - Rapport de calibrage `reports/exit_calibration.md` via `uv run rugby-risk report exits`.

