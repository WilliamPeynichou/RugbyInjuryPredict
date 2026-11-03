# F26 — API FastAPI

| Champ | Valeur |
|---|---|
| Phase | 7 |
| Dépendances | F25 |
| Estimation | M |
| Docs de référence | `docs/03-architecture.md` §2.7, `docs/07-legal-rgpd.md` §2 |

## Objectif

Exposer en lecture seule les sorties publiques (courbes, incidences, calibration, modèle) via une API documentée, utilisée par le front.

## Contexte

L'API ne lit que les tables publiques de Supabase. Elle ne peut structurellement pas renvoyer de donnée nominative.

## Périmètre

- [ ] Ajouter `fastapi`, `uvicorn`, `httpx` (déjà présent).
- [ ] `api/main.py`, `api/deps.py` (client Supabase lecture seule, clé anonyme), `api/schemas.py` (Pydantic), `api/routes/`.
- [ ] Endpoints :
  - `GET /health`
  - `GET /v1/models` — versions publiques et métriques
  - `GET /v1/positions` — postes, groupes, libellés FR
  - `GET /v1/curves?position=HOOKER&scenario=median&model_version=latest` — h(N) avec intervalles
  - `GET /v1/curves/compare?positions=PROP,WING&scenario=…`
  - `GET /v1/cumulative?position=…&scenario=…&k=5` — risque cumulé sur K matchs (calculé depuis la courbe)
  - `GET /v1/incidence?season=2025-2026` — incidence par poste
  - `GET /v1/calibration?model_version=…`
  - `GET /v1/scenarios` — liste et description des scénarios
- [ ] Validation stricte des paramètres (poste ∈ vocabulaire contrôlé, `k ≤ 15`).
- [ ] Cache HTTP (`Cache-Control: public, max-age=3600`), CORS limité au domaine du front.
- [ ] Middleware de sécurité : chaque réponse JSON est inspectée ; présence d'une clé de `FORBIDDEN_PUBLIC_COLUMNS` → erreur 500 et log d'alerte.
- [ ] OpenAPI exporté dans `web/openapi.json` (`make openapi`) pour générer le client TypeScript (F27).
- [ ] `Dockerfile` minimal pour l'API.

## Hors périmètre

- Authentification (API publique en lecture seule). Endpoint nominatif (interdit).

## Fichiers

| Fichier | Action |
|---|---|
| `src/rugby_risk/api/{__init__,main,deps,schemas,security}.py`, `src/rugby_risk/api/routes/*.py` | créer |
| `Dockerfile.api` | créer |

## Tests

- `tests/unit/api/test_routes.py` — `TestClient` avec un dépôt de données factice : chaque endpoint, paramètres invalides → 422.
- `tests/unit/api/test_security.py` — une réponse contenant `player_key` est bloquée par le middleware.
- `tests/unit/api/test_cumulative.py` — calcul du risque cumulé.

## Critères d'acceptation

- [ ] `make api` démarre et `/docs` affiche l'OpenAPI.
- [ ] Couverture ≥ 85 % sur `api/`.
- [ ] `make check` vert.

## Journal

