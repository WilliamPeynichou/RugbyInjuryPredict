# CLAUDE.md — Instructions pour Claude Code

Ce fichier est lu automatiquement par Claude Code à chaque session. Il définit **comment travailler** sur ce dépôt. Le **quoi** est dans `docs/` et `features/`.

## 1. Mission du projet

Construire un système qui estime, **par poste**, la probabilité qu'un joueur professionnel de rugby (Top 14 + matchs internationaux + coupes d'Europe) se blesse au prochain match, en fonction :
- du **nombre de matchs consécutifs** joués ;
- de la **charge de matchs passée** (minutes sur 7/14/28/56/365 jours, internationaux inclus) ;
- des **antécédents de blessure** et du contexte (repos, surface, phase de saison, fenêtres internationales).

Le livrable principal est une **courbe de risque calibrée h(N) par poste** (risque au match N+1 après N matchs consécutifs), avec intervalles d'incertitude. Ce n'est **pas** un outil de prédiction nominatif.

Lire dans l'ordre avant de coder : `README.md` → `docs/00-vision.md` → `docs/03-architecture.md` → `docs/04-data-model.md` → `features/ROADMAP.md`.

En cas d'erreur, de doute ou de blocage, consulter d'abord le document de recherche situé à la racine Git (`Prédire le risque de blessure par poste et enchaînement de matchs en Top 14 _ données, science et architecture.md`, nom de fichier Unicode décomposé), puis ses sources et les alternatives proposées. Vérifier les affirmations avant usage ; les règles de conformité et le schéma contractuel de `docs/` restent prioritaires. Poser une question seulement si le point reste bloquant.

## 2. Workflow obligatoire : une feature à la fois

1. Ouvrir `features/ROADMAP.md`. Choisir la **première feature au statut `todo` dont toutes les dépendances sont `done`**.
2. Lire **intégralement** sa fiche `features/Fxx-*.md` et les docs qu'elle référence.
3. Passer le statut à `in_progress` dans `ROADMAP.md`.
4. Créer une branche `feat/Fxx-slug`.
5. Implémenter **uniquement le périmètre** de la fiche (section « Hors périmètre » respectée).
6. Écrire les tests listés dans la fiche **avant ou avec** le code. Jamais de réseau dans les tests : utiliser les fixtures de `tests/fixtures/`.
7. Lancer `make check` (lint + types + tests). Tout doit être vert.
8. Cocher chaque critère d'acceptation dans la fiche (`- [x]`). Si un critère ne peut pas être tenu, l'écrire dans la section « Journal » de la fiche, avec la raison.
9. Passer le statut à `done` dans `ROADMAP.md`, commit en Conventional Commits : `feat(F05): ingest allrugby player match minutes`.
10. Résumer en 5 lignes max ce qui a été fait et ce qui reste ouvert.

Si une fiche est ambiguë ou contradictoire avec `docs/`, **`docs/` fait foi** pour les règles (conformité, schéma), **la fiche fait foi** pour le périmètre. En cas de doute bloquant, s'arrêter et poser la question plutôt que deviner.

Commande raccourcie disponible : `/feature F05` (voir `.claude/commands/feature.md`).

## 3. Règles d'or (non négociables)

1. **Anti-fuite temporelle.** Toute feature d'un joueur-match est calculée avec des données strictement antérieures au coup d'envoi (`as_of_ts`). Aucune information post-match dans les features. Un test dédié le vérifie (F17).
2. **Validation temporelle uniquement.** Jamais de k-fold aléatoire sur des lignes joueur-match. Split par saison (rolling origin), voir `docs/06-modeling.md`.
3. **Données de santé = RGPD art. 9.** Une blessure liée à un joueur identifié est une donnée de santé. Les tables d'apprentissage utilisent un `player_key` pseudonymisé. L'API et le front **n'exposent que des agrégats par poste ou groupe de postes**, jamais un risque nominatif. Voir `docs/07-legal-rgpd.md`.
4. **Respect des sources.** Aucune collecte réseau sur une source dont `authorized: false` dans `config/sources.yaml`. Le client HTTP refuse l'appel (F01, F03). Respect de robots.txt, débit limité, User-Agent identifiable.
5. **Idempotence.** Rejouer une partition (saison/journée) ne crée aucun doublon. Upserts sur clés naturelles.
6. **Lac brut immuable.** Chaque réponse HTTP est stockée telle quelle (compressée + hash + horodatage + URL) avant parsing. On re-parse sans re-scraper.
7. **Pas de ratio ACWR** comme feature centrale. Charges aiguës et chroniques entrées séparément.
8. **Calibration avant discrimination.** La métrique de sélection de modèle est la log-loss / le Brier score en validation temporelle, pas l'AUC.
9. **Pas de secrets dans le code.** Tout passe par `.env` (non commité) et `src/rugby_risk/settings.py` (pydantic-settings).

## 4. Stack

| Couche | Outil |
|---|---|
| Langage | Python 3.12, gestion par `uv` |
| Qualité | `ruff` (lint + format), `mypy --strict` sur `src/`, `pytest`, `pytest-cov` |
| Orchestration | Dagster (assets, partitions saison/journée) |
| Collecte | `httpx` async, `selectolax` (HTML), Playwright en dernier recours |
| Validation | Pydantic v2 (entités), Pandera (DataFrames) |
| Stockage analytique | Parquet (lac) + DuckDB |
| Transformations | dbt-core + dbt-duckdb |
| Résolution d'entités | Splink (backend DuckDB) |
| Extraction blessures | API LLM (modèle configurable par `LLM_MODEL`), sortie structurée Pydantic |
| Modèles | statsmodels, scikit-learn, PyMC + bambi, LightGBM, lifelines, SHAP |
| Suivi d'expériences | MLflow (tracking local `mlruns/` puis serveur) |
| Service | Supabase Postgres (tables agrégées), FastAPI |
| Front | Next.js (App Router, TypeScript), déployé sur Vercel |

## 5. Structure du dépôt (cible)

```
rugby-injury-risk/
├── CLAUDE.md, README.md, Makefile, pyproject.toml, .env.example
├── config/                  # sources.yaml, seasons.yaml, settings par environnement
├── data/
│   ├── raw/                 # lac brut immuable (gitignored)
│   ├── reference/           # CSV versionnés : postes, compétitions, stades, surfaces, calendrier tests, listes protégées
│   └── warehouse.duckdb     # (gitignored)
├── src/rugby_risk/
│   ├── settings.py
│   ├── http/                # client poli, cache, stockage brut, garde-fous sources
│   ├── sources/             # un sous-module par source : lnr/, allrugby/, espn/, worldrugby/, news/
│   ├── parsers/             # HTML/JSON → modèles Pydantic
│   ├── entity_resolution/
│   ├── injuries/            # signaux, extraction LLM, fusion, annotation
│   ├── features/            # helpers Python si besoin hors dbt
│   ├── modeling/            # baselines, hazard, selection, hierarchical, gbm, severity, validation
│   ├── serving/             # export Supabase, batch predictions
│   └── api/                 # FastAPI
├── orchestration/           # définitions Dagster
├── dbt/                     # projet dbt (staging, marts, ml)
├── web/                     # Next.js
├── notebooks/               # exploration uniquement, jamais importés par src/
├── tests/                   # unitaires + intégration, fixtures/ (HTML/JSON figés)
├── docs/
└── features/
```

## 6. Commandes

```bash
make setup        # uv sync + pre-commit install + playwright install (optionnel)
make check        # ruff check + ruff format --check + mypy + pytest
make test         # pytest -q (hors slow et network)
make test-slow    # tests marqués slow (MCMC, intégration lourde)
make dagster      # dagster dev -m orchestration
make seeds        # copie data/reference/ vers dbt/seeds/
make dbt          # cd dbt && dbt build
make mlflow       # mlflow ui --backend-store-uri ./mlruns
make api          # uvicorn rugby_risk.api.main:app --reload
make openapi      # exporte l'OpenAPI de FastAPI vers web/openapi.json
make web          # cd web && pnpm dev
make check-web    # pnpm lint + typecheck + test
make purge-health # suppression des données nominatives de blessure (confirmation requise)
```

## 7. Conventions de code

- Identifiants en anglais, docstrings et commentaires en français ou anglais (cohérent par fichier).
- Fonctions pures pour le parsing et le feature engineering ; les effets de bord (réseau, disque) sont isolés dans `http/` et les assets Dagster.
- Un parseur = un module = un fichier de tests avec au moins 2 fixtures réelles figées (dont un cas limite).
- Dates : `datetime` timezone-aware en UTC dans le stockage, conversion Europe/Paris à l'affichage uniquement.
- Noms de postes : vocabulaire contrôlé de `data/reference/positions.csv` (voir `docs/04-data-model.md`). Ne jamais écrire un poste en dur ailleurs.
- Logs structurés (`structlog`), pas de `print`.
- Détails dans `docs/08-conventions.md`.

## 8. Ce que Claude Code ne doit pas faire

- Lancer un scraping massif « pour tester ». Les tests tournent sur fixtures ; les runs réels passent par Dagster avec une partition explicite.
- Publier ou logger des données de blessure nominatives hors du lac et de l'entrepôt local.
- Modifier `docs/07-legal-rgpd.md` ou `config/sources.yaml` (`authorized`) sans demande explicite de l'humain.
- Ajouter une dépendance lourde non listée en section 4 sans le justifier dans le journal de la fiche.
