# F21 — Modèle de sélection et pondération IPW

| Champ | Valeur |
|---|---|
| Phase | 5 |
| Dépendances | F20 |
| Estimation | M |
| Docs de référence | `docs/06-modeling.md` §1, §3.3, `docs/02-science-priors.md` §3, §6 |

## Objectif

Modéliser la probabilité qu'un joueur éligible joue (`π(t)`) et corriger le biais de sélection (« survivant en bonne santé ») du hazard par pondération inverse (M1w).

## Contexte

Les joueurs qui enchaînent sont les plus robustes, et les staffs mettent au repos les joueurs fatigués avant qu'ils ne se blessent. Sans correction, l'effet des longues séquences est sous-estimé, voire inversé.

## Périmètre

- [x] `modeling/selection.py` : `SelectionModel` (régression logistique régularisée, ou LightGBM calibré si mieux en log-loss) prédisant `played` sur **toutes** les lignes éligibles, avec les features as-of (pas d'information du match `t`).
- [x] Exclusion des absences de motif connu non-blessure (`international_duty` vu du club, `suspension`) de l'ensemble de risque ou en covariable — choix argumenté dans le journal.
- [x] Poids stabilisés `w = P̂(played) / π̂(t)` avec `P̂(played)` estimé par poste ; troncature aux percentiles 1 et 99 ; diagnostics (distribution des poids, ESS effectif).
- [x] Les poids sont calculés **dans chaque fold** avec le modèle de sélection entraîné sur le train du fold uniquement.
- [x] `DiscreteHazardModel` (F20) accepte `weights` ; config `m1w_hazard_ipw.yaml`.
- [x] Rapport comparatif M1 vs M1w : coefficients de charge, courbes h(N) superposées par poste, métriques.
- [x] Analyse de sensibilité : troncature 5–95, sans stabilisation.

## Hors périmètre

- Méthodes causales avancées (g-formula, modèles structuraux marginaux complets) : piste
  notée pour F22+ — voir Journal (point de méthode sur l'estimand).

## Spécification technique

Calibration du modèle de sélection vérifiée (pente ∈ [0,8 ; 1,2]) avant usage des poids : sinon l'IPW est désactivé pour le fold et un avertissement est loggé.

## Fichiers

| Fichier | Action |
|---|---|
| `src/rugby_risk/modeling/selection.py` | créer |
| `src/rugby_risk/modeling/hazard.py` | modifier (poids) |
| `configs/experiments/m1w_hazard_ipw.yaml` | créer |

## Tests

- `tests/unit/modeling/test_selection_bias.py` — simulation : fragilité latente qui réduit `π` et augmente `h` ; le M1 naïf sous-estime l'effet des séquences, M1w s'en rapproche (erreur relative réduite d'au moins 50 %).
- `tests/unit/modeling/test_weights.py` — stabilisation, troncature, ESS.
- `tests/integration/modeling/test_m1w_run.py` — run complet.

## Critères d'acceptation

- [x] Test de simulation du biais vert.
- [x] Rapport M1 vs M1w généré.
- [x] `make check` vert.

## Journal

### 2026-11-08 — F21 livrée (M1w : hazard + IPW de sélection)

**Livré.** `modeling/selection.py` : `SelectionSpec` (18 features as-of du registre,
validation contre les colonnes interdites), `SelectionModel` (régression logistique L2,
transformations apprises sur le train du fold uniquement), calibration cross-fittée par
blocs contigus, `stabilized_weights` (stabilisation par poste sur l'éligible, troncature
aux quantiles du train, ESS), `WeightedHazardModel` (M1w) avec gate de calibration
(pente ∈ [0,8 ; 1,2], sinon IPW désactivé pour le fold + avertissement dans le rapport) et
refit M1 non pondéré interne pour la comparaison. `hazard.py` : `fit(..., sample_weight=)`
vraisemblance de Bernoulli pondérée via la forme binomiale groupée `endog = [y·w, (1−y)·w]`,
poids suivis dans le bootstrap joueur des courbes. `runner.py` : hook `requires_eligible` →
le modèle reçoit TOUTES les lignes éligibles du train du fold (jamais valid/test).
Registry : `m1w_hazard_ipw`, `m1w_hazard_ipw_t95`, `m1w_hazard_ipw_raw` (un nom par variante
car `run_id = f"{name}-{timestamp}"` : deux variantes finies la même seconde s'écrasent —
collision réellement observée). Config `configs/experiments/m1w_hazard_ipw.yaml`. Tests :
`test_weights.py` (6), `test_selection_bias.py` (4), `test_m1w_run.py` (3, dont schéma dbt
réel). Rapports : `reports/experiments/m1w_hazard_ipw-20261108T115414Z.md` (+ `_t95`, `_raw`)
avec figure `*_hazard_curves_ipw.png` (h(N) M1 en pointillés vs M1w).

**Choix argumentés.**
1. *Absences de motif connu non-blessure* : `absence_reason` n'est pas matérialisé par match
   (`fact_eligibility.absence_reason` est un `null::varchar`, le signalement vit en `runs`).
   **Choix : covariables** (`intl_window`, `protected_list` comme proxies observés du devoir
   international) plutôt qu'exclusion, qui aurait exigé un `absence_reason` par match dans le
   mart ml (changement de modèle de données, hors périmètre F21). Suspensions : non
   identifiables → écart data ajouté à docs/10 (S14).
2. *Calibration cross-fittée* : la pente in-sample d'une LR régularisée est biaisée vers 1 ;
   la gate utilise des blocs contigus (ordre préservé). Découpage manuel : le token `KFold`
   est interdit dans `modeling/` par `test_no_random_kfold` (garde-fou anti-split aléatoire).
3. *Simulation du biais* : premier DGP tenté (fragilité latente qui raccourcit les séquences)
   **ne créait aucun biais conditionnel** — conditionner sur `played` n'induit une distorsion
   du coefficient de X que si la sélection dépend de X ET d'une variable Z corrélée au
   risque (collider). DGP retenu : X ⊥ Z dans la population éligible, π = f(X, Z) observé,
   y = g(X, Z). **Point de méthode** : l'IPW restaure la *population éligible* ; avec un
   modèle incomplet (Z omis), le coefficient structurel de X n'est pas identifiable —
   l'estimand de M1w est l'association de la population éligible, pas un effet causal.
   g-formula/MSM : pistes si un estimand causal devient nécessaire.
4. *Troncature* : défaut 1–99 (docs/06). La simulation montre que 1–99 écrête la queue de
   poids qui porte la correction quand la sélection est forte (erreur résiduelle ×0,6–0,7) ;
   0,1–99,9 la ramène sous ×0,5 ; quasi sans troncature, surcorrection (bruit des poids
   extrêmes, ESS effondré). Sensibilité systématique sur les vraies données avec t95.
5. *statsmodels 0.15* : `GLM.fit(freq_weights=...)` et `var_weights` **laissent les
coefficients Bernoulli inchangés** (vérifié contre une duplication exacte des lignes : le
MLE pondéré diffère). Contourné par la forme binomiale groupée `[y·w, (1−y)·w]`, qui
reproduit exactement le MLE pondéré. Écart contourné ajouté à docs/10 (S13).

**Résultats réels** (`dataset_version e8591d016b97059bae784a823a81b005`, train 2022-23,
test 2024-25, 7 819 lignes, prévalence 1,71 % ; tous les folds : pente de calibration de la
sélection 0,995 → gate ouvert, IPW actif partout) :

| Modèle | Log-loss | Brier | Brier skill vs M0 | ROC AUC | Incid. prédite | ESS/n |
|---|---|---|---|---|---|---|
| M1 cloglog | 0,0983 | 0,01704 | +0,0071 | 0,49 | 1,36 % | — |
| M1w (1–99, stab.) | 0,1043 | 0,01726 | −0,0055 | 0,50 | 1,39 % | 0,74 |
| M1w t95 | 0,1018 | 0,01712 | +0,0024 | 0,50 | 1,33 % | 0,80 |
| M1w non stabilisé | 0,1044 | 0,01727 | −0,0060 | 0,50 | 1,39 % | 0,73 |

- Direction attendue : les coefficients de charge **montent** avec IPW (ex. `min_28d`
spline 1 : 0,36 → 0,69 ; spline 2 : 0,79 → 1,21 ; splines de `consecutive_matches`
majoritairement à la hausse, Δ jusqu'à +0,61) — cohérent avec la correction d'un biais du
survivant qui atténue la charge.
- Métriques prédictives : M1w est légèrement **moins bon** que M1 (log-loss +0,006 ; écarts
de Brier bien dans l'IC90 bootstrap). Attendu : l'IPW coûte ~25 % d'ESS et vise l'estimand,
pas la prédiction ; avec une seule saison d'estimation le surcoît de variance domine. t95 est
la variante la moins coûteuse.
- **Conclusion** : M1w est l'instrument de correction d'estimation ; la décision M1 vs M1w
pour le modèle de production est à F22 (hiérarchique), où les poids se combineront aux priors.

**Écarts / incidents.** S13 (statsmodels `freq_weights` ignoré, contourné), S14
(`absence_reason` non matérialisé par match). Session parallèle détectée sur la machine
(rapports `constant` et runs sur un export `b9a4b4fb` transitoire) : les runs de comparaison
ont été relancés proprement et tous les chiffres ci-dessus portent le même `dataset_version`.

**Non vérifié / risques**
- IPW corrigé pour la sélection sur observables seulement ; une sélection sur fragilité non
  mesurée reste (bornée par la simulation : correction partielle, jamais négative).
- Avec 5 saisons de train (crawl 2018-2022) la balance variance/biais changera ; re-décider
  M1 vs M1w (et la troncature) en F22.
- Le gate est cross-fitté sur le train du fold ; un dérive temporelle forte de la sélection
  (convention FFR/LNR 2026) peut le fermer — c'est voulu (IPW désactivé + avertissement).

