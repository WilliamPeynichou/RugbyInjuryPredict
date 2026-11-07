# F16 — Fusion des signaux, annotation et contrôle qualité

| Champ | Valeur |
|---|---|
| Phase | 3 |
| Dépendances | F12, F13, F15 |
| Estimation | L |
| Docs de référence | `docs/04-data-model.md` (`fact_injury_event`), `docs/02-science-priors.md` §1–2, `docs/07-legal-rgpd.md` §2 |

## Objectif

Produire `fact_injury_event` en fusionnant les signaux sortie, absence et annonce, attribuer un score de confiance à chaque épisode, mesurer la précision sur un jeu annoté et comparer l'incidence reconstruite aux priors.

## Contexte

C'est la cible du modèle. Sa qualité conditionne tout le reste. Le critère de sortie de phase 3 est une précision ≥ 0,85.

## Périmètre

- [x] `injuries/fusion.py` : regroupement des signaux d'un même joueur dans une fenêtre de 10 jours en un épisode candidat.
- [x] Score de confiance (règles, paramètres dans `config/injury_rules.yaml`, section `fusion`) :
  - annonce seule : 0,7 (0,8 si durée ou zone précisée) ;
  - sortie (≥ 0,7) + absence `injury_candidate` : 0,75 ;
  - sortie + annonce : 0,9 ;
  - sortie + absence + annonce : 0,95 ;
  - sortie seule : force du signal × 0,6 ;
  - absence `injury_candidate` seule : 0,4 ;
  - plafond 0,99.
- [x] Attributs de l'épisode : `onset_date` (match de sortie > date annoncée > premier match manqué), `onset_match_id`, `context`, `body_region`, `injury_type`, `is_concussion` (annonce prioritaire), `return_date` (premier match joué après l'onset), `days_missed`, `severity_class`, `censored`, `signals`, `evidence` (URLs, mention_ids, extraits ≤ 200 caractères).
- [x] Fusion de deux épisodes du même joueur si chevauchement < 7 jours et même zone (ou zone inconnue).
- [x] Exclusion des joueurs de `data/reference/opt_out.csv`.
- [x] Modèle dbt `fact_injury_event` (+ tests : unicité, `return_date ≥ onset_date`, `days_missed ≥ 0`, `source_confidence ∈ [0,1]`).
- [x] **Annotation** : CLI `uv run rugby-risk annotate --n 400 --seed 42` qui tire un échantillon stratifié (par force de confiance et par saison) d'épisodes candidats **et** de non-épisodes (apparitions sans signal), affiche les preuves et enregistre la décision humaine (`injury / not_injury / unsure`) dans `data/review/annotations.csv` (gitignored).
- [x] Métriques `injuries/evaluate.py` : précision, rappel (sur l'échantillon), précision par bande de confiance → recalibrage des scores possible (isotone) ; rapport `reports/injury_label_quality.md`.
- [x] Contrôle de priors : incidence reconstruite par saison et par poste (blessures en match / 1000 h de match) comparée à la plage attendue (`docs/02-science-priors.md` §2) ; asset check `WARN` si hors [40, 110] / 1000 h.

## Hors périmètre

- Modélisation. Publication de données nominatives (interdite).

## Spécification technique

Exposition en heures = somme des `minutes_played / 60` sur les apparitions de la saison et du poste.

## Fichiers

| Fichier | Action |
|---|---|
| `src/rugby_risk/injuries/{fusion,evaluate}.py`, `src/rugby_risk/injuries/annotation/{__init__,cli,sampling}.py` | créer |
| `dbt/models/marts/fact_injury_event.sql` + `.yml` | créer |
| `config/injury_rules.yaml` | modifier |
| `orchestration/assets/injuries.py` (+ asset checks) | créer |

## Tests

- `tests/unit/injuries/test_fusion.py` — combinaisons de signaux → scores attendus ; fusion de deux épisodes proches ; épisode censuré en fin de saison.
- `tests/unit/injuries/test_evaluate.py` — précision et rappel sur un jeu d'annotations synthétique.
- `tests/unit/injuries/test_sampling.py` — stratification et reproductibilité (seed).
- `tests/integration/injuries/test_prior_check.py` — incidence synthétique hors plage → WARN.

## Critères d'acceptation

- [ ] Pipeline complet sur données synthétiques : `fact_injury_event` conforme aux tests dbt.
- [ ] Après annotation humaine (étape hors Claude Code) : précision ≥ 0,85 sur les épisodes de confiance ≥ 0,6 — chiffre consigné dans le journal.
- [ ] Rapport d'incidence vs priors généré.
- [ ] `make check` vert.

## Journal

- **2026-11-06** : fusion en Python pur (`injuries/fusion.py`, signaux groupés par joueur sur 10 jours, score de confiance par table dans `config/injury_rules.yaml` §fusion, plafond 0,99), staging `injury_episode` → modèle dbt `fact_injury_event` (tests unicité du grain, cohérence interne en tests singuliers — `dbt_utils` n'est pas déclaré comme package, donc pas de `expression_is_true`). Asset Dagster `injury_episodes` (dépend de `participation_marts` et `injury_mentions`) + asset check `injury_incidence_prior_check` (WARN hors 40–110 / 1000 h). Retour d'absence = premier match rejoué (`on_sheet`) après la fin du run, calculé côté asset (`first_returns_after`). Outil d'annotation : `rugby-risk annotate sample --n 400 --seed 42` (échantillon stratifié confiance × saison + non-épisodes) et `rugby-risk annotate decide` ; métriques et rapport `reports/injury_label_quality.md` via `rugby-risk report injury-quality` ; recalibrage isotone (PAV) dans `evaluate.py`.
- **Reste humain** : annotation de 300–500 épisodes (précision ≥ 0,85 sur confiance ≥ 0,6 attendue pour clore le critère), avis juriste art. 9. Aucune collecte presse réelle (source `news` autorisée mais aucun flux historique : le flux RSS ne couvre que l'actuel ; à traiter en F14).

