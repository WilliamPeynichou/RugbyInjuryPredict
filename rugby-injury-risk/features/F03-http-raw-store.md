# F03 — Client HTTP poli et lac brut

| Champ | Valeur |
|---|---|
| Phase | 1 |
| Dépendances | F01 |
| Estimation | M |
| Docs de référence | `docs/03-architecture.md` §2.1, `docs/01-data-sources.md` §2, `CLAUDE.md` règles 4 et 6 |

## Objectif

Fournir l'unique point d'accès réseau du projet : un client asynchrone qui refuse les sources non autorisées, limite son débit, respecte robots.txt, met en cache, et archive chaque réponse dans un lac brut immuable.

## Contexte

Toutes les ingestions (F05–F08, F14) passent par ce client. Les tests ne touchent jamais le réseau : `respx` simule les réponses.

## Périmètre

- [ ] `PoliteClient` (async context manager) : garde-fou `assert_authorized` avant chaque requête, limiteur par hôte, robots.txt (cache 24 h, refus si disallow), retries exponentiels (429/5xx uniquement, respect de `Retry-After`), timeout 30 s, User-Agent construit depuis les settings.
- [ ] Cache conditionnel : stocke ETag / Last-Modified par URL canonique, envoie `If-None-Match` / `If-Modified-Since`, sur 304 renvoie le contenu du lac.
- [ ] `RawStore` : écriture `data/raw/<source>/<yyyy>/<mm>/<sha256>.<ext>.zst` + append dans `data/raw/_manifest.parquet`. Écriture atomique (fichier temporaire puis rename). Jamais de réécriture d'un hash existant.
- [ ] `canonicalize_url(url)` : tri des paramètres, suppression des fragments et des paramètres de tracking (`utm_*`).
- [ ] Mode `offline` (settings) : le client ne lit que le lac, utile pour re-parser.
- [ ] CLI `uv run rugby-risk raw ls --source allrugby` (liste du manifeste).

## Hors périmètre

- Playwright (ajouté plus tard dans une source si indispensable, avec justification dans le journal).
- Parsing.

## Spécification technique

```python
@dataclass(frozen=True)
class FetchResult:
    source: str
    url: str
    status: int
    content: bytes
    content_type: str
    sha256: str
    fetched_at: datetime
    from_cache: bool


class PoliteClient:
    def __init__(
        self, source_id: str, settings: Settings | None = None, store: RawStore | None = None
    ): ...
    async def get(self, url: str, *, params: dict[str, str] | None = None) -> FetchResult: ...


class RawStore:
    def put(self, result: FetchResult) -> Path: ...
    def get_latest(self, source: str, url: str) -> FetchResult | None: ...
    def iter_manifest(self, source: str | None = None) -> Iterator[ManifestRow]: ...
```

Manifeste : `source, url_canonical, fetched_at, status, sha256, content_type, size_bytes, etag, last_modified`.

## Fichiers

| Fichier | Action |
|---|---|
| `src/rugby_risk/http/{__init__,client,store,robots,ratelimit,urls}.py` | créer |
| `src/rugby_risk/cli.py` | créer (Typer ou argparse ; Typer si ajouté avec justification) |

## Tests

- `tests/unit/http/test_guard.py` — source non autorisée : aucun appel émis (respx vérifie 0 appel), exception levée.
- `tests/unit/http/test_ratelimit.py` — deux requêtes successives espacées d'au moins `min_delay_seconds` (horloge simulée).
- `tests/unit/http/test_robots.py` — URL interdite par robots.txt → refus.
- `tests/unit/http/test_retry.py` — 503 puis 200 → succès ; 404 → pas de retry.
- `tests/unit/http/test_store.py` — écriture idempotente (même contenu → même fichier, une ligne de manifeste par fetch), décompression identique, 304 servi depuis le lac.
- `tests/unit/http/test_urls.py` — canonicalisation.

## Critères d'acceptation

- [ ] Impossible d'émettre une requête vers une source `authorized: false` (test).
- [ ] Le lac est en append-only (test qui tente une réécriture → exception).
- [ ] Couverture ≥ 90 % sur `http/`.
- [ ] `make check` vert.

## Journal

