# 08 — Conventions

## 1. Python

- Python 3.12, gestion par `uv` (`uv add`, `uv sync`, `uv run`).
- Paquet unique `rugby_risk` sous `src/` (layout src).
- `ruff` : `line-length = 100`, règles `E,F,I,B,UP,SIM,RUF,N,PL` (ajuster `PLR0913` si besoin).
- `mypy --strict` sur `src/` ; `tests/` en mode normal.
- Typage complet, `from __future__ import annotations` inutile en 3.12 sauf cas cyclique.
- Pas de `print` : `structlog.get_logger(__name__)`.
- Exceptions métier dans `src/rugby_risk/errors.py` (`SourceNotAuthorizedError`, `ParseError`, `QualityCheckError`, `LeakageError`, `PrivacyViolationError`).
- Constantes de domaine : jamais en dur. Postes → `data/reference/positions.csv` via `rugby_risk.reference.positions()`. Priors → `rugby_risk.modeling.priors`.

## 2. Données

- Dates stockées en UTC (`TIMESTAMPTZ`), conversion Europe/Paris uniquement à l'affichage.
- `season_id` au format `YYYY-YYYY` (ex. `2025-2026`).
- Parquet : compression `zstd`, partitionnement `source=`, `season=`.
- DataFrames : Polars ou pandas acceptés ; à l'interface d'un module public, documenter le type. Validation Pandera sur les DataFrames qui traversent une frontière de couche.

## 3. dbt

- Nommage : `stg_<source>__<entity>`, `int_<entity>__<transformation>`, `dim_<entity>`, `fact_<entity>`, `ml_<table>`.
- Chaque modèle de marts a un `.yml` avec description et tests sur toutes les clés.
- SQL en minuscules, CTE nommées, une CTE `final` en fin de modèle.
- Pas de logique métier dans `staging/` (typage, renommage, déduplication uniquement).

## 4. Tests

- `pytest` ; marqueurs : `unit`, `integration`, `slow`, `network` (le marqueur `network` est **exclu** de `make check` et de la CI).
- Fixtures réelles figées dans `tests/fixtures/<source>/` (HTML/JSON), nommées `<cas>.<ext>`, accompagnées d'un `README.md` qui indique la date de capture et l'URL d'origine.
- Données synthétiques : `tests/factories.py` (générateur de saisons fictives avec blessures simulées à taux connus) — sert à tester la chaîne de modélisation de bout en bout (F18).
- Couverture minimale : 80 % sur `src/rugby_risk/` hors `api/` et `orchestration/`.
- Tout bug corrigé → un test de non-régression.

## 5. Git

- Branche par feature : `feat/Fxx-slug`.
- Conventional Commits avec scope feature : `feat(F05): …`, `fix(F09): …`, `test(F17): …`, `docs(F29): …`, `chore: …`.
- Un merge = une feature terminée, `make check` vert, critères cochés.
- Interdits au commit (hook pre-commit) : `data/raw/`, `data/staging/`, `*.duckdb`, `.env`, `mlruns/`, fichiers > 5 Mo.

## 6. Fiches features

- Une fiche = un périmètre livrable en une session ou deux.
- Le journal en bas de fiche consigne décisions, écarts, dettes techniques.
- Les critères d'acceptation sont vérifiables (commande, test, chiffre), jamais subjectifs.

## 7. Front (`web/`)

- Next.js App Router, TypeScript strict, ESLint + Prettier, pnpm.
- Composants serveur par défaut ; client uniquement pour l'interactivité (simulateur).
- Aucun appel direct à une table nominative ; client typé généré depuis l'OpenAPI de FastAPI.
- Accessibilité : contrastes AA, graphiques avec tableau alternatif.
