# F00 — Bootstrap du dépôt

| Champ | Valeur |
|---|---|
| Phase | 0 |
| Dépendances | — |
| Estimation | M |
| Docs de référence | `CLAUDE.md` §4–7, `docs/03-architecture.md` §4, `docs/08-conventions.md` |

## Objectif

Disposer d'un dépôt Python installable, testable et vérifiable en une commande (`make check`), avec la structure cible vide.

## Contexte

Toutes les autres features supposent ce socle : layout `src/`, settings, logs, erreurs métier, CI, hooks de protection des données.

## Périmètre

- [x] `pyproject.toml` géré par `uv` : Python 3.12, dépendances de base (`httpx`, `selectolax`, `pydantic>=2`, `pydantic-settings`, `structlog`, `polars`, `duckdb`, `pyyaml`, `pandera`) ; groupe `dev` (`ruff`, `mypy`, `pytest`, `pytest-cov`, `pytest-asyncio`, `respx`, `pre-commit`, `types-PyYAML`). Les dépendances lourdes (dagster, dbt, splink, pymc, lightgbm, mlflow, fastapi) sont ajoutées par les features qui les utilisent.
- [x] Arborescence cible de `CLAUDE.md` §5 avec `__init__.py` et `.gitkeep`.
- [x] `src/rugby_risk/settings.py` (pydantic-settings, lecture `.env` + `config/settings.<env>.yaml`), `src/rugby_risk/logging.py` (structlog JSON en prod, console en dev), `src/rugby_risk/errors.py` (exceptions de `docs/08-conventions.md` §1).
- [x] `.env.example` avec toutes les variables de `docs/03-architecture.md` §4 (valeurs vides).
- [x] `Makefile` avec toutes les cibles de `CLAUDE.md` §6 (`setup`, `check`, `test`, `test-slow`, `dagster`, `seeds`, `dbt`, `mlflow`, `api`, `openapi`, `web`, `check-web`, `purge-health`) ; celles dont l'outil n'est pas encore installé affichent « disponible après Fxx ».
- [x] `.gitignore` : `data/raw/`, `data/staging/`, `data/review/`, `*.duckdb`, `.env`, `mlruns/`, `web/node_modules/`, `web/.next/`.
- [x] `.pre-commit-config.yaml` : ruff, ruff-format, check-added-large-files (5 Mo), hook local qui refuse tout fichier sous `data/raw|data/staging` ou finissant par `.duckdb`.
- [x] CI GitHub Actions `.github/workflows/ci.yml` : `uv sync`, `make check` (sans marqueur `network`).
- [x] `pytest.ini_options` : marqueurs `unit`, `integration`, `slow`, `network` ; `-m "not network and not slow"` par défaut (`make test-slow` lance `-m slow`).

## Hors périmètre

- Configuration des sources (F01), données de référence (F02), Dagster (F05), dbt (F04).

## Spécification technique

```python
# settings.py
class Settings(BaseSettings):
    env: Literal["dev", "prod", "test"] = "dev"
    data_dir: Path = Path("data")
    warehouse_path: Path = Path("data/warehouse.duckdb")
    http_contact: str = ""
    pseudonym_salt: SecretStr = SecretStr("")
    llm_api_key: SecretStr = SecretStr("")
    llm_model: str = ""
    supabase_url: str = ""
    supabase_service_key: SecretStr = SecretStr("")
    mlflow_tracking_uri: str = "./mlruns"
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")


def get_settings() -> Settings: ...  # lru_cache
```

## Fichiers

| Fichier | Action |
|---|---|
| `pyproject.toml`, `uv.lock`, `Makefile`, `.env.example`, `.gitignore`, `.pre-commit-config.yaml` | créer |
| `.github/workflows/ci.yml` | créer |
| `src/rugby_risk/{__init__,settings,logging,errors}.py` | créer |
| Arborescence vide (`config/`, `data/reference/`, `orchestration/`, `dbt/`, `web/`, `notebooks/`, `tests/fixtures/`) | créer |

## Tests

- `tests/unit/test_settings.py` — lecture d'un `.env` temporaire, valeurs par défaut, secrets non affichés dans `repr`.
- `tests/unit/test_logging.py` — un log produit un JSON valide en mode prod.
- `tests/unit/test_gitignore.py` — les motifs sensibles sont présents dans `.gitignore`.

## Critères d'acceptation

- [ ] `make setup && make check` passe sur une machine vierge.
- [x] `uv run python -c "import rugby_risk"` fonctionne.
- [ ] La CI est verte sur la branche.
- [x] Un `git add data/raw/x.txt` est bloqué par le hook pre-commit.

## Journal

- Python 3.12 et les dépendances installés ; `make setup` et `make check` passent localement. Le test utilise `git add -f` suivi du hook : sans `-f`, `.gitignore` refuse déjà le fichier.
- La racine Git est le répertoire parent : la CI et le hook tiennent compte du chemin `rugby-injury-risk/`.
- Validation finale locale : `make setup` et `make check` réussis, 18 tests, couverture 88,37 %. Ruff du hook aligné sur la version installée ; configuration invalide et protection des fichiers testées sans réseau.
- F00 livrée avec réserves documentées : CI distante non exécutée (aucun push effectué) et machine distincte non disponible. Ces critères restent volontairement décochés ; les commandes équivalentes ont été validées localement.

