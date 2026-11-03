# F06 — Ingestion LNR (feuilles de match)

| Champ | Valeur |
|---|---|
| Phase | 1 |
| Dépendances | F03, F04 |
| Estimation | M |
| Docs de référence | `docs/01-data-sources.md` §1–2, `docs/07-legal-rgpd.md` §3 |

## Objectif

Récupérer les compositions officielles LNR (XV de départ, banc, poste, identifiant joueur stable) pour servir d'**ancre de résolution d'entités** et de contrôle croisé des feuilles allrugby.

## Contexte

Les CGU LNR sont restrictives : la collecte doit rester ponctuelle et n'est lancée qu'avec autorisation. On ne récupère que ce qui est nécessaire à la réconciliation (compositions, ID, poste, nationalité).

## Périmètre

- [x] `sources/lnr/urls.py` : `top14.lnr.fr/feuille-de-match/{saison}/j{journée}/{id}-{dom}-{ext}/compositions` ; découverte des matchs par journée (page calendrier).
- [x] `parsers/lnr/lineup.py` → `StagingMatch` + `list[StagingAppearance]` (minutes `NULL` : la LNR sert pour composition et ID) + `StagingPlayerProfile` partiel (ID LNR, nom, nationalité, poste).
- [x] Asset Dagster `lnr_staging_lineups` partitionné par saison et journée (`MultiPartitionsDefinition`).
- [x] Rapport de cohérence `lnr_vs_allrugby` (asset) : pour chaque match présent dans les deux sources, comparer la liste des 23 ; sortie Parquet `data/staging/_reports/lineup_diff/`.
- [x] Fixtures : 3 feuilles de match (régulière, phase finale, feuille avec changement tardif).

## Hors périmètre

- Statistiques de temps de jeu LNR, classements, contenus éditoriaux.

## Spécification technique

- `source_player_id` = identifiant joueur LNR extrait du lien de profil.
- Normalisation des postes bruts LNR vers `position_code` via une table de correspondance `data/reference/position_aliases.csv` (créée ici : `raw_label, source, position_code`).
- `PARSER_VERSION = "lnr-1"`.

## Fichiers

| Fichier | Action |
|---|---|
| `src/rugby_risk/sources/lnr/*`, `src/rugby_risk/parsers/lnr/*` | créer |
| `orchestration/assets/lnr.py` | créer |
| `data/reference/position_aliases.csv` | créer |
| `tests/fixtures/lnr/*` | créer |

## Tests

- `tests/unit/parsers/test_lnr_lineup.py` — 23 joueurs, 15 titulaires, ID LNR extraits, postes normalisés.
- `tests/unit/test_position_aliases.py` — tout alias pointe vers un `position_code` valide.
- `tests/integration/test_lineup_diff.py` — deux sources synthétiques avec une différence connue → la différence est rapportée.

## Critères d'acceptation

- [x] Partition `(2024-2025, J10)` matérialisable en offline sur fixtures.
- [x] Le rapport de diff identifie correctement un joueur absent d'une source.
- [x] `make check` vert.

## Journal

- **Activation humaine de `lnr`** (demande explicite de l'utilisateur, 2026-11-03), dans le cadre tracé par le document de recherche : exception de fouille de textes et de données (art. L.122-5-3 CPI), recherche non commerciale sans redistribution, collecte polie (robots.txt respecté, `min_delay_seconds: 5.0`, UA identifiable), sous réserve d'absence d'opt-out. Décision et cadre consignés dans `notes_legal` de `config/sources.yaml`. Tests F01 mis à jour pour refléter la décision (les autres sources restent refusées).
- Fixtures LNR construites à la main (3 feuilles) : hypothèses de balisage listées dans le module parseur ; à valider au premier crawl réel (limité à la réconciliation, pas de statistiques de temps de jeu).
- Postes normalisés via `data/reference/position_aliases.csv` (alias LNR → `position_code`), validée contre `positions.csv` par test.
- Partitions `MultiPartitionsDefinition` saison × journée ; clé de partition : `J10|2024-2025` (dimensions ordonnées alphabétiquement).
- Asset `lnr_vs_allrugby` : diff sur (équipe, nom normalisé sans accents, n° de maillot) → Parquet `data/staging/_reports/lineup_diff/`. Les deux côtés d'une différence sont rapportés.
- `make check` vert : 117 tests, couverture 90,73 %. CI distante non exécutée. Aucun crawl réel lancé.
