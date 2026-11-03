# F25 — Prédictions batch et export Supabase agrégé

| Champ | Valeur |
|---|---|
| Phase | 7 |
| Dépendances | F22 |
| Estimation | M |
| Docs de référence | `docs/04-data-model.md` §5, `docs/07-legal-rgpd.md` §2, `docs/03-architecture.md` §2.7 |

## Objectif

Calculer les sorties publiques du modèle de production (courbes h(N) par poste et scénario, incidence par poste et saison, calibration, métadonnées du modèle) et les publier dans Supabase, avec un garde-fou d'agrégation infranchissable.

## Contexte

C'est la frontière entre le monde nominatif (local) et le monde public. Tout ce qui la franchit doit être agrégé (k ≥ 10 joueurs distincts) et dépourvu d'identifiant.

## Périmètre

- [ ] Ajouter `supabase` (client Python) ou `psycopg` (connexion Postgres directe) — choix justifié.
- [ ] Migrations SQL `supabase/migrations/0001_public_tables.sql` : tables de `docs/04-data-model.md` §5, RLS activée, lecture anonyme seule sur ces tables, aucune écriture publique.
- [ ] `serving/batch.py` : charge le modèle **promu** (registre MLflow, alias `production`), calcule :
  - `pred_position_curve` pour N = 0..15, chaque poste, chaque scénario de `configs/scenarios.yaml` ;
  - `pred_position_season` (incidence observée et prédite par poste et saison, nombre de blessures en tranches : `<10`, `10-24`, `25-49`, `50+`) ;
  - `calibration_public`, `model_registry_public`.
- [ ] `serving/guard.py` :
  - `FORBIDDEN_PUBLIC_COLUMNS = {player_key, player_id, full_name, source_player_id, birth_date, …}` ;
  - `enforce_aggregation(df, min_support=10)` supprime toute ligne avec `n_players_support < 10` ;
  - `assert_public_safe(df)` lève `PrivacyViolationError` si une colonne interdite est présente ;
  - appelés systématiquement avant toute écriture.
- [ ] `serving/export.py` : upsert idempotent par (`model_version`, clés métier).
- [ ] Asset Dagster `public_predictions` (dépend de `ml_player_match` et du registre) et job `publish`.
- [ ] Mode `--dry-run` : écrit des CSV dans `reports/public_preview/` au lieu de Supabase.

## Hors périmètre

- API (F26). Front (F27).

## Fichiers

| Fichier | Action |
|---|---|
| `supabase/migrations/0001_public_tables.sql` | créer |
| `src/rugby_risk/serving/{__init__,batch,guard,export}.py` | créer |
| `orchestration/assets/publish.py` | créer |

## Tests

- `tests/unit/serving/test_guard.py` — colonne interdite → exception ; cellule à 9 joueurs supprimée, à 10 conservée.
- `tests/unit/serving/test_batch.py` — avec un modèle factice, les tables produites ont le schéma attendu et ne contiennent aucune colonne interdite.
- `tests/integration/serving/test_export_dry_run.py` — dry-run idempotent (deux runs → mêmes CSV).
- `tests/integration/serving/test_migrations.py` (optionnel, Postgres local via `testcontainers` si disponible, sinon marqueur `slow`).

## Critères d'acceptation

- [ ] Aucun chemin de code n'écrit dans Supabase sans passer par `assert_public_safe` et `enforce_aggregation` (test d'architecture : grep des appels d'écriture).
- [ ] Dry-run complet sur données synthétiques.
- [ ] `make check` vert.

## Journal

