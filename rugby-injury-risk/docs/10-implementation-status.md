# 10 — Journal d'implémentation (état des lieux)

État au 2026-11-03 (F00–F07). Statut détaillé et à jour des features : `features/ROADMAP.md`
(statuts) et le **Journal** de chaque fiche `features/Fxx-*.md` (décisions, écarts).

## Vue d'ensemble

| Phase | Features | Statut |
|---|---|---|
| 0 — Socle | F00 bootstrap, F01 registre sources, F02 données de référence | ✅ fait |
| 1 — Collecte/entrepôt | F03 HTTP + lac brut, F04 DuckDB/dbt, F05 ingestion allrugby, F06 ingestion LNR | ✅ fait |
| 2 — Internationaux/coupes/entités | F07 internationaux ✅ fait ; F08, F09 | 🟡 en cours |
| 3+ | F10 → F29 | ⬜ à faire |

`make check` vert : ruff, format, mypy strict, pytest (131 tests, couverture ~92 %).
Branches : une `feat/Fxx-*` par feature, commits Conventional Commits.

## Ce qui existe, en une ligne chacun

- **F00 — Bootstrap** : dépôt `uv` (Python 3.12), `make check` (ruff + format +
  mypy strict + pytest, cov ≥ 80 %), hook pre-commit (secrets, gros fichiers),
  `tests/unit/test_gitignore.py` et `test_sensitive_files.py` qui verrouillent
  `.gitignore` et l'interdiction de committer `.env`, `data/raw`, `data/staging`,
  `*.duckdb`, `mlruns/`.
- **F01 — Registre sources** : `config/sources.yaml` (9 sources, `authorized`
  strict, garde-fou `assert_authorized`), `config/seasons.yaml` (2013-14 →
  2026-27, validées : bornes 1er juillet–30 juin, non-chevauchement, flag COVID).
- **F02 — Données de référence** : `data/reference/` (9 postes / 6 groupes /
  2 unités, compétitions, 24 stades, surfaces 2025-26 confirmées par la page
  LNR APPE, fenêtres de tests 2013–2027, historique des régimes de protection
  FFR/LNR). Chargeurs Polars + Pandera, cache, clones. Été 2020 sans fenêtre
  (COVID, accepté humainement). Trous non sourcés documentés dans le README de
  `data/reference/`.
- **F03 — Client HTTP poli + lac brut** : `PoliteClient` (refus des sources non
  autorisées et des hôtes non déclarés, rate-limit par hôte, robots.txt cache
  24 h, retries 429/5xx avec `Retry-After`, timeout 30 s, UA identifiable),
  cache conditionnel ETag/Last-Modified, mode `offline`, `RawStore` append-only
  (zstd, écriture atomique, manifeste Parquet, jamais de réécriture d'un hash),
  canonicalisation d'URL, CLI `rugby-risk raw ls`. Tests sans réseau (respx).
- **F04 — Entrepôt DuckDB + dbt** : projet `dbt/` (seeds `ref_*` générés par
  `make seeds`, dimensions `dim_competition/season/venue/venue_surface`,
  staging `stg_match/appearance/player_profile` lisant le Parquet ou relation
  vide typée), `warehouse.py` (`connect`, `write_staging` partitionné
  `source=/season=` avec validation Pandera, `upsert` idempotent),
  `staging_schemas.py` (contrats F05–F08), `privacy.py` (HMAC-SHA256,
  sel vide refusé hors `test`) enregistré comme UDF DuckDB via un plugin
  dbt-duckdb — Python et dbt produisent la même clé (testée). `make dbt` vert.
- **F05 — Ingestion allrugby** : URLs, découverte saison→matchs→joueurs (live),
  parseurs match (titulaires 1–15, banc, minutes, cartons, quarantaine si
  feuille invalide) et joueur (profil complet ou partiel), coup d'envoi
  Europe/Paris via `zoneinfo` avec heure imputée 15:00 + flag
  `kickoff_time_imputed`. Dagster : partitions par saison, assets staging
  recalculables **offline depuis le lac brut** ; `make dagster` les matérialise.
  Fixtures construites à la main (source non autorisée) — hypothèses de
  balisage listées dans `tests/fixtures/allrugby/README.md`.
- **F06 — Ingestion LNR** : `lnr` **activée par décision humaine** (2026-11-03)
  dans le cadre fouille de textes et de données (art. L.122-5-3 CPI), recherche
  non commerciale, sans redistribution, collecte polie (`min_delay: 5 s`,
  robots respecté), consigné dans `notes_legal`. Parseur de compositions (ID
  LNR, postes normalisés via `position_aliases.csv`, minutes `NULL`), partitions
  `(saison, journée)`, asset de rapport `lnr_vs_allrugby` →
  `data/staging/_reports/lineup_diff/`. 3 fixtures manuelles.
- **F07 — Internationaux** : parseurs World Rugby (summary + timeline → minutes
  reconstruites : `Sub On/Off`, `IR`/`HIAO` en bascule, rouge = sortie) et ESPN
  (compositions, minutes `NULL`), mapping `competition_aliases.csv` + repli par
  mois, exclusion féminin/7/jeunes, assets `intl_staging_worldrugby`,
  `intl_staging_espn` (offline, par saison) et rapport `intl_minutes_check` →
  `data/staging/_reports/intl_minutes/`. Sources live codées mais non autorisées ;
  fixtures JSON anonymisées générées par script.

## Autorisations de collecte (état réel)

| Source | `authorized` | Note |
|---|---|---|
| lnr | ✅ true | Décision humaine 2026-11-03, cadre documenté dans `notes_legal`. Aucun crawl réel lancé. Consigne : si la LNR bloque (refus, robots, 403/429 persistants), on garde ce qui est déjà collecté à date, sans contournement. |
| allrugby, itsrugby, espn, worldrugby, apisports, sportradar, wikipedia, news | ❌ false | F03 lève `SourceNotAuthorizedError` avant tout appel réseau (testé). |

API retenue pour le calendrier (F08) : **API-Sports** (freemium selon le document
de recherche ; quotas non vérifiés ; clé à fournir hors dépôt).

## Décisions et écarts structurants (détails dans les Journaux de fiches)

1. **Pseudonymisation dbt = même fonction Python** (plugin dbt-duckdb), pas de
   table de correspondance : impossible de diverger.
2. **Pas de `sources.yml` dbt** pour le Parquet : un glob vide fait échouer
   DuckDB ; la macro `read_staging` renvoie une relation vide typée.
3. **Seeds dbt ignorés par git** : `make seeds` les régénère depuis
   `data/reference/` (NULL → cellule vide).
4. **selectolax en backend lexbor** (modest déprécié par la version installée).
5. **mypy strict assoupli sur `orchestration/`** (`[[tool.mypy.overrides]]`) ;
   `src/` reste strict.
6. **Cast Polars 2** : dtypes Pandera convertis via `v.type` dans
   `warehouse.staging_frame` (centralisé, gère les frames vides).
7. **Assets de staging Dagster = offline** : recalculés depuis le lac brut
   (manifeste), jamais de réseau ; seul l'asset `*_raw_pages` est live.
8. **Clé de partition multi** : dimensions ordonnées alphabétiquement
   (`J10|2024-2025`).
9. **Heure imputée** : coup d'envoi sans heure → 15:00 Europe/Paris +
   `kickoff_time_imputed` (colonne ajoutée au contrat `StagingMatch`).
10. **Fixture-first** : allrugby et LNR développés sur fixtures figées ; le
    balisage réel reste à valider au premier crawl autorisé.
11. **ESPN sans minutes** (F07) : le recoupement inter-sources compare la taille
    des feuilles ; l'écart de minutes (> 5 %) est contrôlé contre 15 × 80.

## Commandes

```bash
make check    # ruff + format + mypy + pytest (gate de qualité)
make dbt      # seeds + dbt build (DuckDB data/warehouse.duckdb)
make dagster  # matérialise les assets staging allrugby (partition 2023-2024)
rugby-risk raw ls --source lnr   # liste le lac brut
```

## Prochaines étapes (ordre ROADMAP)

1. **F08** — coupes d'Europe + calendrier (API-Sports, nécessite clé + décision
   d'activation).
2. **F09** — résolution d'entités (ancre LNR), puis F10 marts de participation.
