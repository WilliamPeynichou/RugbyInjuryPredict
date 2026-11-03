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

- [ ] `sources/lnr/urls.py` : `top14.lnr.fr/feuille-de-match/{saison}/j{journée}/{id}-{dom}-{ext}/compositions` ; découverte des matchs par journée (page calendrier).
- [ ] `parsers/lnr/lineup.py` → `StagingMatch` + `list[StagingAppearance]` (minutes `NULL` : la LNR sert pour composition et ID) + `StagingPlayerProfile` partiel (ID LNR, nom, nationalité, poste).
- [ ] Asset Dagster `lnr_staging_lineups` partitionné par saison et journée (`MultiPartitionsDefinition`).
- [ ] Rapport de cohérence `lnr_vs_allrugby` (asset) : pour chaque match présent dans les deux sources, comparer la liste des 23 ; sortie Parquet `data/staging/_reports/lineup_diff/`.
- [ ] Fixtures : 3 feuilles de match (régulière, phase finale, feuille avec changement tardif).

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

- [ ] Partition `(2024-2025, J10)` matérialisable en offline sur fixtures.
- [ ] Le rapport de diff identifie correctement un joueur absent d'une source.
- [ ] `make check` vert.

## Journal

