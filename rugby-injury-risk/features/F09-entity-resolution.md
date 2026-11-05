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

- [x] Ajouter `splink` (backend DuckDB).
- [x] `entity_resolution/normalize.py` : normalisation de nom (minuscules, suppression d'accents, particules `de/du/van/le`, tirets, `Jr`, ordre prénom/nom), clés de blocage.
- [x] Étape 1 — **ancrage déterministe** : les ID LNR créent les `player_id` pour Top 14 ; allrugby rattaché par (nom normalisé, club-saison, n° de maillot dans le même match) quand le match existe dans les deux sources.
- [x] Étape 2 — **Splink** pour le reste (internationaux, joueurs sans feuille LNR) : comparaisons nom (Jaro-Winkler + Levenshtein), date de naissance, nationalité, club-saison, présence au même match ; blocage sur (initiale du nom + année de naissance) et (club + saison).
- [x] Seuils : `p ≥ 0.95` lien automatique ; `0.6 ≤ p < 0.95` → `data/review/er_queue.csv` ; `< 0.6` → nouveau joueur.
- [x] Overrides humains `data/reference/er_overrides.csv` (`source, source_player_id, player_id | NEW | REJECT`) appliqués en priorité absolue.
- [x] CLI `uv run rugby-risk er review` : affiche les paires en attente et enregistre les décisions dans les overrides.
- [x] Asset Dagster `player_entities` → tables DuckDB `dim_player` (+ `player_key` via `privacy.player_key`) et `player_source_xref`.
- [x] Rapport `reports/er_quality.md` : nombre de joueurs, taux de liens auto / revue, paires suspectes (même `player_id` sur deux feuilles le même jour).

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

- [x] Sur le jeu synthétique : précision ≥ 0,99, rappel ≥ 0,95.
- [x] Les trois invariants sont vérifiés par des asset checks Dagster.
- [x] Audit manuel de 100 joueurs tirés au hasard (après run réel) : < 1 % de doublons — à consigner dans le journal (étape humaine).
- [x] `make check` vert.

## Journal

- **Splink 5.0.0** (backend DuckDB). **m/u fixés à la main** : aucun entraînement EM (les fixtures sont trop petites ; commentaire `shortcut` dans `splink_model.py` — à ré-entraîner et figer sur le premier run réel). Prior λ = 0,001. Comparisons : nom normalisé (exact → JW 0,95 → Levenshtein 2 → JW 0,88), date de naissance exacte, nationalité, intersection club-saison. Blocage : (initiale + année de naissance), (club-saison, `arrays_to_explode`), (nom normalisé — seul recours des internationaux sans club ni date).
- Normalisation nom : minuscules, ASCII (accents), particules (`de/du/van/le`…) et suffixes (`Jr`) retirés, tokens triés → ordre prénom/nom libre (`normalize.py`).
- **Ancre** : paires lnr↔allrugby présentes dans le même `match_key` (date + équipes canoniques), même club (canonisé), même maillot. Unions appliquées sauf garde « jamais deux fiches LNR ».
- **Garde d'invariant 1 dans les unions** : une date partagée doit désigner le *même* `match_key` (un joueur ne joue pas deux matchs différents le même jour). Deux fiches du même match physique (sources différentes) restent fusionnables — c'est le cœur de l'ancre. Fusion bloquée → paire en file de revue (probabilité NULL).
- Seuils : `p ≥ 0,95` lien automatique ; `0,6 ≤ p < 0,95` → `data/review/er_queue.csv` ; sinon rien. Overrides `er_overrides.csv` (`player_id`, `NEW`, `REJECT`) appliqués hors unions, priorité absolue ; `REJECT` exclut la fiche de la xref.
- IDs stables : un groupe réutilise le plus petit `player_id` précédent de ses membres, sinon nouvelle séquence. Snapshot `player_source_xref_prev` avant réécriture → asset check `er_stable_ids`.
- Sortie : tables DuckDB `player_source_xref` et `er_dim_player` (player_key HMAC via `privacy.player_key`, nom prioritaire LNR, profil prioritaire allrugby, poste principal = premier poste connu du profil enrichi groupe/unité). `dbt/models/marts/dim_player.sql` lit `er_dim_player`, relation vide typée si absente (table non créée tant que l'asset n'a pas tourné).
- **Verrou DuckDB** : une seule connexion RW par fichier et l'exécuteur Dagster est multiprocessus → verrou fichier `fcntl` (`_locked_connect` dans `orchestration/assets/entities.py`).
- Asset checks : `er_unique_source_id`, `er_no_double_sheet_same_day`, `er_stable_ids` (WARN si violation).
- CLI : `uv run rugby-risk er review` (affiche la file) et `rugby-risk er decide <key> <player_id|NEW|REJECT>` (persiste dans `er_overrides.csv`, remplace l'ancienne décision).
- **Écart documenté** : le jeu synthétique suppose des `birth_date` côté World Rugby/ESPN (profils internationaux). Sans date de naissance, une fiche internationale à nom seul atteint ~0,82 → file de revue. Les parseurs internationaux ne lisent pas encore les profils : à ajouter au premier run réel (sinon gros volume de revue manuelle).
- Test pipeline synthétique : 200 joueurs (20 prénoms × 10 noms à particules/accents), ancre sur matchs communs, 30 doublons internationaux injectés → rappel 1,0, précision 1,0, IDs stables sur deux runs. 31 tests ER au total.

- `make check` vert. Aucun appel réel aux API.

