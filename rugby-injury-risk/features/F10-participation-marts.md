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

- [ ] `int_match__reconciled` : fusion multi-sources des matchs (clé naturelle), priorité des sources (F08).
- [ ] `int_appearance__reconciled` : fusion allrugby (minutes) + LNR (composition, poste) + internationaux ; résolution `player_id` via `player_source_xref` ; poste joué = source > n° de maillot (1–15) > poste principal.
- [ ] Déduction `minute_on` / `minute_off` depuis minutes et statut titulaire ; `off_reason = 'card'` si carton rouge ; le reste `unknown` (enrichi par F12).
- [ ] `fact_squad_membership` : appartenance club × saison déduite des apparitions (première et dernière apparition, élargies au début et à la fin de saison sauf transfert observé en cours de saison).
- [ ] `fact_eligibility` : produit `squad_membership × matchs du club` + matchs internationaux où le joueur figure sur la feuille ; `on_sheet`, `played`, `absence_reason = NULL` (rempli par F13).
- [ ] Tests dbt :
  - unicité des clés, relations ;
  - 15 titulaires et ≤ 8 remplaçants par équipe et par match ;
  - somme des minutes par équipe ∈ [1 100, 1 300] (15 × 80 ± cartons et temps additionnel) ;
  - minutes ∈ [0, 100] ;
  - aucun joueur sur deux feuilles le même jour.
- [ ] Rapport de couverture `reports/coverage.md` : matchs par saison et compétition, % de matchs avec minutes, % passant le contrôle des minutes.

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

- [ ] `make dbt` vert sur les données de fixtures.
- [ ] Mini-saison synthétique : `fact_eligibility` identique à l'attendu ligne à ligne.
- [ ] Rapport de couverture généré.
- [ ] `make check` vert.

## Journal

