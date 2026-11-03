# F01 — Registre des sources et configuration

| Champ | Valeur |
|---|---|
| Phase | 0 |
| Dépendances | F00 |
| Estimation | S |
| Docs de référence | `docs/01-data-sources.md` §1–2, `docs/07-legal-rgpd.md` §3 |

## Objectif

Centraliser la description et le statut d'autorisation de chaque source dans `config/sources.yaml`, chargé et validé par un modèle Pydantic, avec un garde-fou réutilisable.

## Contexte

Règle d'or n°4 : aucune collecte réseau sur une source non autorisée. Ce registre est la source de vérité que F03 consultera avant chaque requête.

## Périmètre

- [ ] `config/sources.yaml` avec les entrées : `allrugby`, `lnr`, `itsrugby`, `espn`, `worldrugby`, `apisports`, `sportradar`, `wikipedia`, `news`.
- [ ] `config/seasons.yaml` : saisons couvertes (`2013-2014` → saison en cours), dates de début/fin, flag COVID.
- [ ] `src/rugby_risk/config/sources.py` : modèles `SourceConfig`, `SourcesRegistry`, fonction `load_sources()`, `assert_authorized(source_id)`.
- [ ] `src/rugby_risk/config/seasons.py` : `load_seasons()`, `season_for_date(d)`.

## Hors périmètre

- Client HTTP (F03). Ne **jamais** passer une source à `authorized: true` : c'est une décision humaine.

## Spécification technique

```yaml
# config/sources.yaml
version: 1
defaults:
  min_delay_seconds: 3.0
  respect_robots: true
  max_retries: 3
sources:
  allrugby:
    authorized: false
    base_url: "https://www.allrugby.com"
    notes_legal: "Autorisation demandée le JJ/MM/AAAA — en attente"
  lnr:
    authorized: false
    base_url: "https://top14.lnr.fr"
    extra_hosts: ["prod2.lnr.fr", "www.lnr.fr"]
    notes_legal: "CGU 16/06/2023 restrictives — accord requis"
  itsrugby:
    authorized: false
    base_url: "https://itsrugby.fr"
    notes_legal: "CGU interdisent extraction substantielle — accord requis"
  espn:
    authorized: false
    base_url: "https://site.api.espn.com"
    min_delay_seconds: 2.0
    notes_legal: "API non documentée — usage recherche à faible débit, à valider"
  worldrugby:
    authorized: false
    base_url: "https://api.wr-rims-prod.pulselive.com"
    notes_legal: "API non documentée — à valider"
  apisports:   { authorized: false, base_url: "https://v1.rugby.api-sports.io", requires_api_key: true }
  sportradar:  { authorized: false, base_url: "https://api.sportradar.com", requires_api_key: true }
  wikipedia:   { authorized: true,  base_url: "https://fr.wikipedia.org", notes_legal: "CC BY-SA" }
  news:
    authorized: false
    feeds: []          # renseigné par l'humain en F14
```

```python
class SourceConfig(BaseModel):
    source_id: str
    authorized: bool
    base_url: HttpUrl
    extra_hosts: list[str] = []
    min_delay_seconds: float = Field(ge=1.0)
    respect_robots: bool = True
    max_retries: int = Field(ge=0, le=5)
    requires_api_key: bool = False
    notes_legal: str = ""


def assert_authorized(source_id: str) -> SourceConfig:
    """Lève SourceNotAuthorizedError si la source est absente ou non autorisée."""
```

Validation : `min_delay_seconds ≥ 1.0` imposé (impossible de configurer un scraping agressif).

## Fichiers

| Fichier | Action |
|---|---|
| `config/sources.yaml`, `config/seasons.yaml` | créer |
| `src/rugby_risk/config/{__init__,sources,seasons}.py` | créer |

## Tests

- `tests/unit/test_sources_config.py` — chargement OK ; source inconnue → erreur ; `authorized: false` → `SourceNotAuthorizedError` ; délai < 1 s refusé.
- `tests/unit/test_seasons.py` — `season_for_date(date(2026, 11, 3)) == "2026-2027"` ; flag COVID sur `2019-2020`.

## Critères d'acceptation

- [ ] Toutes les sources sauf `wikipedia` sont `authorized: false` dans le fichier commité.
- [ ] `assert_authorized("lnr")` lève l'exception.
- [ ] `make check` vert.

## Journal

