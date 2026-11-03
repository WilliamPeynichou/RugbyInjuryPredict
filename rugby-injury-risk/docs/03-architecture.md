# 03 — Architecture technique

## 1. Vue d'ensemble

```
[Sources]                    [Ingestion]                [Stockage]                     [Modèles]                 [Produit]
allrugby / LNR / itsrugby    Dagster assets             data/raw/ (immuable)           dbt ml → ml_player_match   FastAPI (lecture seule)
ESPN / World Rugby       →   httpx poli + cache     →   Parquet staging            →   MLflow (expériences)    →  Next.js (Vercel)
Presse / points médicaux     selectolax / Playwright    DuckDB + dbt (étoile)          PyMC / bambi, LightGBM     Supabase (agrégats)
Données de référence (CSV)   Extraction LLM blessures   Supabase Postgres (service)    lifelines, statsmodels
```

Principe directeur : **chaque couche est rejouable indépendamment**. On re-parse depuis le lac brut sans re-scraper ; on reconstruit l'entrepôt depuis le staging ; on réentraîne depuis la table ML figée (hash de version).

## 2. Couches

### 2.1 Collecte (`src/rugby_risk/http/`, `src/rugby_risk/sources/`)

- `PoliteClient` (F03) : `httpx.AsyncClient` avec :
  - garde-fou `authorized` lu depuis `config/sources.yaml` (exception `SourceNotAuthorizedError` **avant** tout appel) ;
  - limiteur de débit par domaine (`min_delay_seconds`) ;
  - lecture et respect de robots.txt (cache 24 h) ;
  - cache conditionnel (ETag / Last-Modified) ;
  - retries exponentiels limités (3) sur 429/5xx, jamais sur 4xx ;
  - User-Agent `rugby-risk-research/<version> (+contact)` depuis les settings.
- `RawStore` (F03) : écrit chaque réponse dans `data/raw/<source>/<yyyy>/<mm>/<sha256>.<ext>.zst` + une ligne dans `data/raw/_manifest.parquet` (`source, url_canonical, fetched_at, status, sha256, content_type, parser_version_hint`). Jamais de suppression ni de réécriture.
- Un module par source dans `sources/<source_id>/` : `urls.py` (construction des URL), `fetch.py` (appels via `PoliteClient`), aucun parsing.

### 2.2 Parsing (`src/rugby_risk/parsers/`)

- Fonctions **pures** : `bytes → list[PydanticModel]`.
- Un champ inattendu ou une page non conforme n'arrête pas le pipeline : l'enregistrement part en quarantaine (`data/staging/_quarantine/`) avec la raison.
- Sortie : Parquet de staging partitionné `data/staging/<entity>/source=<s>/season=<YYYY-YYYY>/`.
- `PARSER_VERSION` constante par module ; la changer déclenche un re-parse complet de la source.

### 2.3 Entrepôt (`dbt/`)

- `dbt-duckdb` lit le staging Parquet via des `sources` externes.
- Couches : `staging/` (nettoyage, typage, 1 modèle par entité source) → `intermediate/` (réconciliation multi-sources, résolution d'entités appliquée) → `marts/` (dimensions, faits) → `ml/` (table d'apprentissage).
- Tests dbt génériques (unique, not_null, relationships, accepted_values) + tests singuliers métier (somme des minutes, 15 titulaires).

### 2.4 Résolution d'entités (`src/rugby_risk/entity_resolution/`)

- Splink (backend DuckDB), Fellegi-Sunter.
- Ancre : identifiant LNR pour Top 14 / Pro D2.
- Sortie : `player_source_xref` avec `match_confidence`. Sous le seuil de revue : file CSV de revue manuelle `data/review/er_queue.csv`, décisions persistées dans `data/reference/er_overrides.csv`.

### 2.5 Blessures (`src/rugby_risk/injuries/`)

- `signals_exit.py`, `signals_absence.py` (SQL dbt + Python), `news_extract.py` (LLM, sortie Pydantic), `fusion.py` (règles + score de confiance), `annotation/` (outil CLI d'annotation, métriques).
- Les données nominatives de blessure ne sortent **jamais** de `data/` et de `warehouse.duckdb`.

### 2.6 Modélisation (`src/rugby_risk/modeling/`)

| Module | Rôle | Feature |
|---|---|---|
| `validation.py` | splits par saison, métriques, calibration, rapports | F18 |
| `priors.py` | constantes de référence | F19 |
| `baselines.py` | Poisson par poste avec offset | F19 |
| `hazard.py` | logistique temps discret, splines, interactions | F20 |
| `selection.py` | modèle de sélection + poids IPW | F21 |
| `hierarchical.py` | PyMC/bambi, effets aléatoires poste/joueur/équipe-saison | F22 |
| `gbm.py` | LightGBM calibré + SHAP | F23 |
| `severity.py` | gravité (jours manqués) | F24 |
| `curves.py` | courbes h(N) par poste avec intervalles | F22, F25 |

Chaque entraînement est loggé dans MLflow : paramètres, `dataset_hash`, métriques par fold, figures de calibration, artefact du modèle.

### 2.7 Service (`src/rugby_risk/serving/`, `src/rugby_risk/api/`)

- `serving/batch.py` : calcule les courbes et agrégats après chaque journée, applique le **garde-fou d'agrégation** (aucune cellule < k = 10 joueurs distincts), pousse dans Supabase.
- Tables Supabase : `pred_position_curve`, `pred_position_season`, `model_registry_public`, `calibration_public`. Aucune table nominative.
- `api/` : FastAPI en lecture seule sur Supabase, cache HTTP, OpenAPI.

### 2.8 Front (`web/`)

Next.js App Router + TypeScript, Recharts ou Visx. Pages : accueil, courbes par poste, simulateur, comparaison priors, méthodologie, à propos. Données servies par l'API (ou client Supabase en lecture seule avec RLS).

### 2.9 Orchestration (`orchestration/`)

Dagster :
- assets partitionnés par `season` (et `round` pour le Top 14) ;
- jobs : `ingest_weekly` (après chaque journée), `rebuild_warehouse`, `train_season` (manuel), `publish` ;
- capteurs de qualité (asset checks) branchés sur les tests dbt et les contrôles de priors.

## 3. Flux de données de bout en bout

1. `ingest_weekly` récupère les pages de la journée → lac brut → parsing → staging.
2. `dbt build` reconstruit staging → marts → `ml_player_match`.
3. `publish` applique le modèle de production figé (registre MLflow) → courbes → Supabase.
4. Fin de saison : `train_season` réentraîne, rapport de calibration, revue humaine, promotion.

## 4. Environnements et configuration

- `.env` : `SUPABASE_URL`, `SUPABASE_SERVICE_KEY`, `LLM_API_KEY`, `LLM_MODEL`, `MLFLOW_TRACKING_URI`, `HTTP_CONTACT`, `PSEUDONYM_SALT`.
- `config/settings.<env>.yaml` pour `dev` / `prod`.
- `src/rugby_risk/settings.py` : `pydantic-settings`, un seul point d'accès.

## 5. Décisions d'architecture (ADR courts)

| # | Décision | Raison |
|---|---|---|
| ADR-1 | Dagster plutôt qu'Airflow | Assets versionnés et partitionnés, intégration dbt, adapté à l'idempotence |
| ADR-2 | DuckDB pour l'analytique, Supabase pour le service | Calcul local rapide de fenêtres glissantes ; seul l'agrégé est exposé |
| ADR-3 | Lac brut immuable | Re-parse sans re-scraper, sobriété vis-à-vis des sources, auditabilité |
| ADR-4 | Hazard en temps discret | Gère covariables dépendantes du temps et événements récurrents simplement |
| ADR-5 | Modèle hiérarchique bayésien en production | Petits effectifs par poste, intervalles crédibles, priors informés |
| ADR-6 | Exposition publique agrégée uniquement | RGPD art. 9, éthique |
| ADR-7 | Pas d'ACWR | Artefacts mathématiques documentés |
