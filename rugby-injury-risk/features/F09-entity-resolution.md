# F09 — Résolution d'entités joueurs

| Champ | Valeur |
|---|---|
| Phase | 2 |
| Dépendances | F05, F06, F07 |
| Estimation | L |
| Docs de référence | `docs/03-architecture.md` §2.4, `docs/04-data-model.md` (`dim_player`, `player_source_xref`) |

## Objectif

Rapprocher les fiches d'un même joueur entre allrugby, LNR, World Rugby et ESPN pour produire `dim_player` et `player_source_xref`, avec un taux de doublons < 1 %.

## Contexte

Un joueur mal rapproché casse ses séquences de matchs (charge club et internationale séparées) et ses antécédents. Risques principaux : homonymes, orthographes multiples (noms fidjiens, samoans, tongiens, géorgiens), accents, particules, transferts.

## Périmètre

- [ ] Ajouter `splink` (backend DuckDB).
- [ ] `entity_resolution/normalize.py` : normalisation de nom (minuscules, suppression d'accents, particules `de/du/van/le`, tirets, `Jr`, ordre prénom/nom), clés de blocage.
- [ ] Étape 1 — **ancrage déterministe** : les ID LNR créent les `player_id` pour Top 14 ; allrugby rattaché par (nom normalisé, club-saison, n° de maillot dans le même match) quand le match existe dans les deux sources.
- [ ] Étape 2 — **Splink** pour le reste (internationaux, joueurs sans feuille LNR) : comparaisons nom (Jaro-Winkler + Levenshtein), date de naissance, nationalité, club-saison, présence au même match ; blocage sur (initiale du nom + année de naissance) et (club + saison).
- [ ] Seuils : `p ≥ 0.95` lien automatique ; `0.6 ≤ p < 0.95` → `data/review/er_queue.csv` ; `< 0.6` → nouveau joueur.
- [ ] Overrides humains `data/reference/er_overrides.csv` (`source, source_player_id, player_id | NEW | REJECT`) appliqués en priorité absolue.
- [ ] CLI `uv run rugby-risk er review` : affiche les paires en attente et enregistre les décisions dans les overrides.
- [ ] Asset Dagster `player_entities` → tables DuckDB `dim_player` (+ `player_key` via `privacy.player_key`) et `player_source_xref`.
- [ ] Rapport `reports/er_quality.md` : nombre de joueurs, taux de liens auto / revue, paires suspectes (même `player_id` sur deux feuilles le même jour).

## Hors périmètre

- Résolution des équipes et stades (alias, F08).

## Spécification technique

Invariants contrôlés après résolution :
1. Un `player_id` n'apparaît jamais sur deux feuilles de match à la même date.
2. Une paire (`source`, `source_player_id`) a exactement un `player_id`.
3. Les `player_id` existants restent stables d'un run à l'autre (table de correspondance persistée, nouveaux ID par séquence).

## Fichiers

| Fichier | Action |
|---|---|
| `src/rugby_risk/entity_resolution/{__init__,normalize,anchor,splink_model,review,invariants}.py` | créer |
| `orchestration/assets/entities.py` | créer |
| `dbt/models/marts/dim_player.sql` (+ `.yml`) | créer (lit la table produite) |

## Tests

- `tests/unit/er/test_normalize.py` — 15 cas réels d'orthographes (accents, particules, translittérations).
- `tests/unit/er/test_anchor.py` — rattachement allrugby ↔ LNR sur un match commun.
- `tests/integration/er/test_pipeline.py` — jeu synthétique de 200 joueurs avec 30 doublons injectés : rappel ≥ 0,95, précision ≥ 0,99 ; override appliqué ; stabilité des ID sur deux runs.
- `tests/unit/er/test_invariants.py` — détection d'un joueur sur deux feuilles le même jour.

## Critères d'acceptation

- [ ] Sur le jeu synthétique : précision ≥ 0,99, rappel ≥ 0,95.
- [ ] Les trois invariants sont vérifiés par des asset checks Dagster.
- [ ] Audit manuel de 100 joueurs tirés au hasard (après run réel) : < 1 % de doublons — à consigner dans le journal (étape humaine).
- [ ] `make check` vert.

## Journal

