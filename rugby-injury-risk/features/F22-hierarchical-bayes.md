# F22 — Modèle hiérarchique bayésien par poste (production)

| Champ | Valeur |
|---|---|
| Phase | 5 |
| Dépendances | F21 |
| Estimation | L |
| Docs de référence | `docs/06-modeling.md` §2 (M2 et priors), §3, §6, `docs/02-science-priors.md` |

## Objectif

Construire le modèle de production M2 : hazard cloglog hiérarchique avec effets par poste partiellement poolés, fragilité joueur et effet équipe-saison, priors informés, poids IPW, et produire les courbes h(N) avec intervalles crédibles.

## Contexte

Petits effectifs par poste, événements rares, structure emboîtée : le cadre bayésien hiérarchique est le plus adapté et donne directement l'incertitude publiée.

## Périmètre

- [x] Ajouter `pymc`, `arviz` (pins `pymc>=5.26.1`, `arviz>=0.22,<1` — arviz 1.x incompatible, journal). **Écart** : ni `bambi` (API inflexible pour l'offset + vraisemblance IPW pondérée, journal) ni sampler externe (`nutpie`/`numpyro` : pas de wheel macOS x86_64 pour `llvmlite`, journal).
- [x] `modeling/hierarchical.py` : `HierarchicalHazardModel` implémentant `RiskModel` :
  - intercept global + écarts `unit` → `position_group` → `position_code` (non centrés) ;
  - pente de `consecutive_matches` (standardisée) par `position_group` partiellement poolée ;
  - effets fixes : splines (B-splines, 3–4 nœuds) sur `apps_20min_365d`, `days_since_last_match_capped` ; **écart** : `min_28d` entre linéairement (le prior Williams 2017 est une pente linéaire qu'une spline ne peut porter, journal) ; `short_turnaround`, `intl_window`, `recent_return_8w`, `n_prior_injuries_365d`, `prior_concussions_365d`, `surface`, `is_playoff`, `season_period` ; termes constants écartés par le design (S12) ;
  - effet aléatoire joueur (`player_key`) et équipe-saison (`team_id|season_id`, nouveau dans le dataset v7, journal) ;
  - offset `log(minutes/80)` ; poids IPW (F21) via vraisemblance pondérée (`pm.Potential`, Bernoulli cloglog pondérée).
- [x] Priors exactement ceux de `docs/06-modeling.md` §2, centralisés dans `modeling/priors.py` (`PRIORS_VERSION = 1.1.0`).
- [x] **Prior predictive check** : incidence simulée par poste dans 30–150 / 1000 h (test automatique sur le modèle compilé).
- [x] Diagnostics : R̂ ≤ 1,01, ESS bulk et tail ≥ 400, 0 divergence ; sinon le run est marqué `failed`.
- [x] Prédiction hors échantillon : joueurs nouveaux → effet joueur intégré par quadrature de Gauss-Hermite (20 nœuds) sur la loi de population N(0, σ²), pas mis à 0 ; les saisons de test sont toujours des équipe-saisons nouvelles.
- [x] Courbes h(N) par `position_code` et scénario avec intervalles crédibles à 90 % (moyenne postérieure sur tirages) → `curves.py` (`DrawCurveModel`).
- [x] Sauvegarde : `InferenceData` NetCDF en artefact MLflow ; enregistrement dans le registre MLflow (`rugby-risk-m2`) **sans** promotion automatique.
- [x] Rapport de revue `reports/model_review_<version>.md` : métriques par fold vs M0/M1/M1w, calibration par groupe, courbes par poste, diagnostics, sensibilités obligatoires (`docs/06-modeling.md` §3.3), critères de rejet (§6) cochés.
- [x] Option `--fast` (sous-échantillonnage stratifié des joueurs par groupe, 2 chaînes, 500 tirages) pour itérer.

## Hors périmètre

- Promotion en production (humaine). Export (F25).

## Spécification technique

Temps de calcul à surveiller : si un fold dépasse 30 min, consigner dans le journal et envisager l'approximation ADVI pour l'exploration (jamais pour la version publiée) ou le sous-échantillonnage des non-événements avec correction d'offset (cas-témoin) documentée.

## Fichiers

| Fichier | Action |
|---|---|
| `src/rugby_risk/modeling/hierarchical.py` | créer |
| `src/rugby_risk/modeling/{priors,curves}.py` | modifier |
| `src/rugby_risk/modeling/review.py` (rapport de revue) | créer |
| `configs/experiments/m2_hierarchical.yaml` | créer |

## Tests

- `tests/unit/modeling/test_prior_predictive.py` — incidence simulée dans la plage.
- `tests/slow/modeling/test_hierarchical_recovery.py` (marqueur `slow`) — données synthétiques avec effets par poste connus : intervalles à 90 % couvrent les vraies valeurs pour ≥ 8 postes sur 9.
- `tests/unit/modeling/test_new_player_prediction.py` — un joueur inconnu reçoit une prédiction finie intégrant la variance de population.
- `tests/integration/modeling/test_m2_fast_run.py` — run `--fast` complet et rapport de revue généré.

## Critères d'acceptation

- [x] Diagnostics MCMC conformes sur le run de référence (R̂ 1,0064, ESS bulk 866 / tail 899, 0 divergence — `target_accept` 0,99, journal).
- [x] Rapport de revue généré avec tous les critères de `docs/06-modeling.md` §6.
- [x] Sur données réelles : pente de calibration par groupe consignée dans le journal ; décision de promotion prise par l'humain (non prise ici : modèle non promu).
- [x] `make check` vert (tests `slow` exécutés séparément via `make test-slow`).

## Journal

### Choix d'implémentation

- **PyMC direct, pas bambi** : l'offset `log(min/80)` et la vraisemblance Bernoulli cloglog pondérée par IPW (`pm.Potential`) ne sont pas expressibles proprement dans l'API formula de bambi ; le coût d'écriture du modèle PyMC est faible et le contrôle total sur les priors (depuis `modeling/priors.py` uniquement) prévaut.
- **Sampler NUTS PyMC (pymc 5.26.1)** : `nutpie` exclu (pas de wheel `llvmlite >= 0.46` pour macOS x86_64) ; `numpyro` écarté pour rester sur un seul backend évalué. `arviz` pin `< 1` (1.x incompatible avec pymc 5.26, `ImportError: concat`).
- **`min_28d` linéaire, pas en spline** : le seul prior informé de charge (Williams 2017, `log(1,14)` par +3,2 FGE / 30 j) est une pente linéaire ; une base spline ne peut le porter. Les splines B restent sur `apps_20min_365d` et `days_since_last_match_capped`.
- **Intégration Gauss-Hermite (20 nœuds)** pour les joueurs / équipe-saisons hors train : exacte à la variance près pour la cloglog (vérifiée contre Monte Carlo à 300 000 tirages, tolérance 0,005), bien moins coûteuse que du MC par prédiction.
- **`target_accept` 0,99 pour la config de production** : à 0,9 le run de référence donnait R̂ max 1,0107 (> 1,01) et 3 divergences ; à 0,99 : R̂ 1,0064, ESS bulk 866 / tail 899, 0 divergence, ~6 min de sampling (vs 2,9 min). Le mode `--fast` conserve 0,9 (exploration).
- **Effet équipe-saison** (`team_id|season_id`) : nécessite la colonne `team_id` dans `ml_player_match` (dataset v7) ; ajoutée au modèle dbt et au registre `ID_COLUMNS`. Ancien dataset `e8591d01` invalidé, v7 = `7d004d9a146715b139e501738e58620a` (53 515 lignes, 17 équipes, 1 034 joueurs).
- **Poids IPW** : extraction mutualisée `fit_ipw_weights` (F21) ; sous PyMC, log-vraisemblance pondérée via `pm.Potential` (pseudo-posterior), Bernoulli cloglog. La variante M2 sans IPW (`m2_hierarchical_noipw`) n'exige pas le frame éligible.

### Résultats sur données réelles (dataset v7, fold test 2024-25)

- Run de référence `m2_hierarchical-20261108T182301Z` : **statut `ok`** (R̂ 1,0064, ESS 866/899, 0 divergence), log-loss pooled 0,0997, prior check 9/9 postes dans la bande 30–150/1000 h.
- Baselines même protocole : M0 log-loss 0,0979, M1 0,0983, M1w 0,1043. Les log-loss sont très resserrés (événements rares, domination par le taux de base) ; la comparaison se fait sur Brier skill et calibration par groupe dans le rapport de revue.
- Run `--fast` : log-loss 0,1019, statut `failed` attendu (seuils §6 non tenus en mode exploration : R̂ 1,0205, ESS 149/111).

### Revue de modèle (docs/06 §3.3 et §6)

Rapport : `reports/model_review_m2_hierarchical-20261108T185750Z.md` (non versionné, dataset v7).

- **Critères §6 tenus** : diagnostics MCMC (R̂ 1,0064, ESS 866/899, 0 divergence), prior predictive 9/9, ROC AUC 0,478 ≤ 0,75 (pas de fuite détectable).
- **Critères §6 NON tenus** : Brier skill −0,0307 (≤ 0 exigé) et pente de calibration hors [0,8 ; 1,2] pour les 6 groupes. À une saison de test et 1,7 % de prévalence, aucun modèle ne domine le taux de base : M0 +0,0001, M1 +0,0071, M1w −0,0055. M1 reste le meilleur Brier skill, sans marge.
- **Sensibilités** : seuil 0,5 et commotions et COVID infaisables (raisons consignées) ; **seuil 0,8 infaisable aussi** — la confiance max de l'export est 0,75 (épisodes ≥ 0,6 seulement matérialisés) ; `y_injury_any_7d` réalisée mais diagnostics `failed` ; **sans IPW réalisée, statut `ok`, Brier skill +0,0035 et log-loss 0,0957 — meilleur que le modèle principal IPW** : avec une seule saison de test, la correction de sélection coûte plus de variance qu'elle n'apporte de biais corrigé.
- Courbes h(N) publiées par poste avec IC90 ; `n_prior_injuries_365d` +0,657 [0,552 ; 0,758] et `recent_return_8w` −1,119 [−1,686 ; −0,620] sont les effets fixes les plus nets ; la pente de `consecutive_matches` par groupe n'est pas identifiable (IC90 tous largement à cheval sur 0, ~390 blessures seulement).
- Décision de promotion : **non cochée, décision humaine** — le rapport est la livraison de F22, pas la promotion.

### Écarts à la fiche

- `age` en spline prévu à l'origine : 100 % NULL sur 2022-2025 (S12) — terme toujours écarté par le design.
- Sensibilité « seuil de confiance 0,8 » : marquée infaisable après plantage initial (« exposition nulle » = zéro épisode ≥ 0,8 ; la confiance max de l'export vaut 0,75). Comportement verrouillé par `tests/unit/modeling/test_review_sensitivities.py`.
- Le rapport de revue et la décision de promotion humaine restent dans `reports/` non versionné ; la promotion n'a pas été demandée et n'est pas automatique.

