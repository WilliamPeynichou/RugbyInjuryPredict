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

- [x] Client d'écriture : **PostgREST via `httpx`** (déjà dépendance du projet) au lieu de `supabase-py`/`psycopg` — aucun driver natif à installer, la clé service ne circule que côté job, les politiques RLS restent dans la migration SQL. Choix justifié (journal).
- [x] Migrations SQL `supabase/migrations/0001_public_tables.sql` : tables de `docs/04-data-model.md` §5, RLS activée, lecture anonyme seule sur ces tables, aucune écriture publique.
- [x] `serving/batch.py` : charge le modèle **promu** (registre MLflow, alias `production`), calcule :
  - `pred_position_curve` pour N = 0..15, chaque poste, chaque scénario de `configs/scenarios.yaml` ;
  - `pred_position_season` (incidence observée et prédite par poste et saison, nombre de blessures en tranches : `<10`, `10-24`, `25-49`, `50+`) ;
  - `calibration_public`, `model_registry_public`.
- [x] `serving/guard.py` :
  - `FORBIDDEN_PUBLIC_COLUMNS = {player_key, player_id, full_name, source_player_id, birth_date, …}` ;
  - `enforce_aggregation(df, min_support=10)` supprime toute ligne avec `n_players_support < 10` ;
  - `assert_public_safe(df)` lève `PrivacyViolationError` si une colonne interdite est présente ;
  - appelés systématiquement avant toute écriture.
- [x] `serving/export.py` : upsert idempotent par (`model_version`, clés métier).
- [x] Asset Dagster `public_predictions` (dépend de `ml_player_match` et du registre) et job `publish`.
- [x] Mode `--dry-run` : écrit des CSV dans `reports/public_preview/` au lieu de Supabase.

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

- [ ] Aucun chemin de code n'écrit dans Supabase sans passer par `assert_public_safe` et `enforce_aggregation` (test d'architecture : grep des appels d'écriture). *Non vérifié à ce jour : ce test d'architecture n'est pas écrit.*
- [ ] Dry-run complet sur données synthétiques. *À confirmer par `tests/integration/serving/test_export_dry_run.py` (en cours).*
- [ ] `make check` vert. *Statut 2026-11-10 : rouge, en réparation ; rien n'est commité.*

**Statut : 🚧 en cours — code écrit, check en réparation (2026-11-10).**

## Journal

- **Implémentation** :
  - `serving/guard.py` : `FORBIDDEN_PUBLIC_COLUMNS` (identifiants, noms, dates de naissance,
    mesures anthropométriques — tout ce qui rapproche d'un individu), `enforce_aggregation`
    (lignes avec moins de 10 joueurs distincts supprimées ; `min_support < 10` refusé),
    `make_public` = point d'entrée unique. Tests : colonne interdite -> exception, 9 supprimé,
    10 conservé.
  - `serving/batch.py` : les 4 tables de docs/04 §5. Courbes h(N) : moyenne et IC90 **par
    tirage postérieur**, plus le risque cumulé sur N+1 matchs calculé par tirage (produit
    1-prod(1-h), bande exacte). Incidence par poste et saison : Poisson exact (Garwood) en
    IC90, effectif de blessures en tranches (`<10`, `10-24`, `25-49`, `50+`). Calibration et
    registre : lus dans les résumés d'expérience `reports/experiments/<run_id>_summary.json`
    (nouveau, écrit par le runner F18 à chaque run : métriques agrégées + bins de calibration
    avec nombre de joueurs distincts par bin). Le fit final (F30) n'est **jamais** noté sur
    ses propres lignes : sans run rolling-origin sur le même `dataset_version`, l'export est
    refusé (`PublishError`). Le `player_key` ne sert qu'à compter les joueurs distincts.
  - `serving/export.py` : `publish()` = seul chemin d'écriture ; chaque table repasse
    `make_public` au sink (garde redondante : un sink n'écrit rien de non revérifié).
    `DryRunSink` : CSV déterministes dans `reports/public_preview/` (idempotent : deux runs,
    mêmes fichiers). `SupabaseSink` : upsert PostgREST ; le CLI et l'asset Dagster **refusent**
    Supabase tant que l'artefact n'a pas de `PROMOTION.md` humain (docs/06 §5).
  - Runner F18 modifié : `_summary_json` (agrégats sans identifiant) ; `calibration_bins`
    (bins quantiles + support joueurs) ; `estimation_rows` (mêmes filtres que les folds :
    l'export agrège exactement la population d'estimation). Tous les modèles relancés pour
    produire les résumés : M0, M1, M1w, M3 (2026-11-09) et M2 référence.
  - `orchestration/assets/publish.py` : asset `public_predictions` (dépend de `ml_table`) ;
    `rugby-risk publish-public --mode dry-run|supabase`.
  - `supabase/migrations/0001_public_tables.sql` : schéma docs/04 §5 + checks `k >= 10` en
    base, RLS activée, politique `select` pour `anon` uniquement, `insert/update/delete`
    révoqués pour `anon` et `authenticated`.
- **Run réel (dry-run)** : `rugby-risk publish-public --mode dry-run` ->
  `reports/public_preview/` : 577 lignes de courbes (9 postes x 4 scénarios x N=0..15),
  28 lignes d'incidence (label ML : centre 29,0/1000h max, talonneur 8,6/1000h min en
  2022-2023, cohérent avec le rapport F19), 41 lignes de calibration, 5 lignes de registre
  (M2 + M0 + M1 + M1w + M3, métriques du test 2024-2025). Modèle **non promu** : le front
  affichera un bandeau explicite.
- **Écarts** : pas de `testcontainers`/Postgres local (optionnel dans la fiche) : les checks
  `k >= 10` sont couverts par la contrainte SQL + les tests du garde Python ; l'upsert
  PostgREST est mocké avec `respx`. Pas de test bout-en-bout `build_public_tables` sur
  l'artefact réel (exige un fit MCMC) : les briques sont testées séparément et le dry-run
  réel ci-dessus valide l'assemblage.
- **Reste** : écrire `PROMOTION.md` (décision humaine après revue F22/F23) pour débloquer
  l'upsert Supabase réel ; F26 lit soit les CSV dry-run (dev) soit Supabase (prod).
