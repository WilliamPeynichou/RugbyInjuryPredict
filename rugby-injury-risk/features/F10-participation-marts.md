# F10 — Marts de participation et éligibilité

| Champ | Valeur |
|---|---|
| Phase | 2 |
| Dépendances | F08, F09 |
| Estimation | L |
| Docs de référence | `docs/04-data-model.md` §2–3, §6, `docs/05-features-spec.md` §2 |

## Objectif

Construire `dim_team`, `fact_match`, `fact_appearance`, `fact_squad_membership` et surtout `fact_eligibility` (joueur × match de son équipe, joué ou non), avec tests de qualité.

## Contexte

C'est **la table la plus importante du projet** : elle fournit les features de charge, le signal d'absence et le dénominateur des modèles. Sans les matchs non joués, impossible de modéliser la sélection ni de calculer les séquences.

## Périmètre

- [x] `int_match__reconciled` : fusion multi-sources des matchs (clé naturelle), priorité des sources (F08).
- [x] `int_appearance__reconciled` : fusion allrugby (minutes) + LNR (composition, poste) + internationaux ; résolution `player_id` via `player_source_xref` ; poste joué = source > n° de maillot (1–15) > poste principal.
- [x] Déduction `minute_on` / `minute_off` depuis minutes et statut titulaire ; `off_reason = 'card'` si carton rouge ; le reste `unknown` (enrichi par F12).
- [x] `fact_squad_membership` : appartenance club × saison déduite des apparitions (première et dernière apparition, élargies au début et à la fin de saison sauf transfert observé en cours de saison).
- [x] `fact_eligibility` : produit `squad_membership × matchs du club` + matchs internationaux où le joueur figure sur la feuille ; `on_sheet`, `played`, `absence_reason = NULL` (rempli par F13).
- [x] Tests dbt :
  - unicité des clés, relations ;
  - 15 titulaires et ≤ 8 remplaçants par équipe et par match ;
  - somme des minutes par équipe ∈ [1 100, 1 300] (15 × 80 ± cartons et temps additionnel) ;
  - minutes ∈ [0, 100] ;
  - aucun joueur sur deux feuilles le même jour.
- [x] Rapport de couverture `reports/coverage.md` : matchs par saison et compétition, % de matchs avec minutes, % passant le contrôle des minutes.

## Hors périmètre

- Motifs d'absence (F13), motifs de sortie (F12).

## Spécification technique

Seuil de qualité bloquant : si moins de 98 % des matchs Top 14 d'une saison passent le contrôle des minutes, l'asset check échoue (sévérité `ERROR`) et la saison est marquée `quality_flag = 'low'` dans `dim_season`.

## Fichiers

| Fichier | Action |
|---|---|
| `dbt/models/intermediate/int_*.sql` | créer |
| `dbt/models/marts/{dim_team,fact_match,fact_appearance,fact_squad_membership,fact_eligibility}.sql` + `.yml` | créer |
| `dbt/tests/*.sql` (tests singuliers) | créer |
| `orchestration/assets/dbt_assets.py` (intégration `dagster-dbt`) | créer |

## Tests

- Tests dbt listés ci-dessus.
- `tests/integration/test_participation_marts.py` — sur une mini-saison synthétique (2 clubs, 6 matchs, 1 transfert, 1 sélection internationale), vérifier exactement le contenu attendu de `fact_eligibility`.

## Critères d'acceptation

- [x] `make dbt` vert sur les données de fixtures.
- [x] Mini-saison synthétique : `fact_eligibility` identique à l'attendu ligne à ligne.
- [x] Rapport de couverture généré.
- [x] `make check` vert.

## Journal

- 2026-11-05 — Livré sur branche `feat/F10-participation-marts`.
  - **Pas de `dagster-dbt`** (dépendance absente de la stack) : asset unique
    `participation_marts` (`orchestration/assets/dbt_assets.py`) qui appelle `dbtRunner`
    (`rugby_risk.marts.build_marts`), sous le verrou fichier de l'entrepôt. Pas de lignage par
    modèle dans Dagster ; passer à `dagster-dbt` en F28 si besoin.
  - **Ids stables** : `match_id` = 15 premiers hex du md5 de la clé naturelle (docs/04 §6),
    `team_id` = 7 hex du md5 du nom canonique. Rejouer = mêmes ids ; collisions couvertes par
    les tests `unique`.
  - **Alias d'équipes en SQL** : `team_aliases.csv` exporté en seed `ref_team_aliases`, macro
    `canonical_team` = même règle que `reference.team_canonical` (alias source, puis `*`,
    sinon nom brut). Dates de match = date UTC (macro `utc_date`).
  - **Bug corrigé** : `read_parquet` détectait le partitionnement Hive et remplaçait la colonne
    `source` par le nom du dossier (`source=all`, `source=espn_europe`). Macro `read_staging`
    en `hive_partitioning = false`.
  - **Écart docs/04** : `fact_appearance.minutes_played` est `NULL` quand aucune source ne donne
    les minutes (LNR, ESPN, World Rugby sans minutes) ; `fact_eligibility.played` est alors
    `true` pour un titulaire, `NULL` pour un remplaçant. Plutôt qu'une valeur inventée.
  - `fact_squad_membership` : apparitions en championnat (`club_domestic`) seulement ; les
    clubs étrangers vus en coupe d'Europe n'ont pas d'effectif (leurs feuilles restent dans
    `fact_eligibility`).
  - `is_playoff` : regex sur le libellé brut de phase (shortcut, vocabulaire contrôlé à venir).
  - `minute_off` seulement pour un titulaire sorti avant 80' ; un remplaçant expulsé n'est pas
    daté (F12 enrichira).
  - Tests singuliers « 15 titulaires / ≤ 8 remplaçants » et « somme des minutes ∈ [1100,
    1300] » en sévérité `warn` : le seuil bloquant est l'asset check `top14_minutes_quality`
    (`ERROR` si une saison Top 14 a < 98 % de matchs conformes, `dim_season.quality_flag =
    'low'`).
  - Rapport `reports/coverage.md` écrit par l'asset (non versionné tant qu'il n'y a pas de run
    réel).

