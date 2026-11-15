# Revue du modèle m2_hierarchical-20261108T185750Z

Association statistique, non causale. Agrégats uniquement — aucune donnée nominative.

- Modèle candidat : `m2_hierarchical` (statut `ok`)
- dataset_version : `7d004d9a146715b139e501738e58620a`
- git_sha : `f94c077891782232c48cf0944e1fb1a3d40e6b37`
- Rapport d'expérience : `reports/experiments/m2_hierarchical-20261108T185750Z.md`
- Artefacts : `m2_hierarchical-20261108T185750Z_idata.nc`

## Critères de rejet (docs/06 §6)

- [ ] Brier skill score > 0 (moyenne des folds) : -0.0307
- [ ] Pente de calibration dans [0.8; 1.2] pour chaque groupe de postes : hors bornes : back_row, back_three, centre, front_row, half_back, lock
- [x] ROC AUC ≤ 0.75 (sinon fuite à expliquer) : 0.478
- [x] Diagnostics MCMC : R-hat ≤ 1,01, ESS bulk/tail ≥ 400, 0 divergence : R-hat 1.0063860875746384, ESS 866.1732546937028 / 898.966712957552, divergences 0
- [x] Prior predictive check : incidence par poste dans 30-150 / 1000 h : True

## Métriques par fold vs M0 / M1 / M1w

| Modèle | Fold | Test | Log-loss | Brier | Brier skill | PR-AUC | ROC AUC | Pente |
|---|---|---|---|---|---|---|---|---|
| m2_hierarchical | 0 | 2024-2025 | 0.0997 | 0.01769 | -0.0307 | 0.0236 | 0.478 | -0.035 |
| m0_position | 0 | 2024-2025 | 0.0979 | 0.01716 | +0.0001 | 0.0120 | 0.346 | -0.685 |
| m1_hazard_cloglog | 0 | 2024-2025 | 0.0983 | 0.01704 | +0.0071 | 0.0282 | 0.490 | -0.012 |
| m1w_hazard_ipw | 0 | 2024-2025 | 0.1043 | 0.01726 | -0.0055 | 0.0408 | 0.504 | 0.075 |

## Calibration par groupe de postes

Voir le rapport d'expérience (section « Calibration par groupe de postes »).

| Groupe | Blessures | Observé | Prédit | Pente |
|---|---|---|---|---|
| back_row | 23 | 0.0150 | 0.0223 | -0.560 |
| back_three | 35 | 0.0291 | 0.0300 | -0.460 |
| centre | 28 | 0.0314 | 0.0342 | -0.025 |
| front_row | 14 | 0.0068 | 0.0088 | 0.522 |
| half_back | 20 | 0.0179 | 0.0261 | 0.083 |
| lock | 14 | 0.0138 | 0.0140 | -1.210 |

## M2 : diagnostics MCMC

| Critère | Valeur | Seuil | OK |
|---|---|---|---|
| R-hat max | 1.0064 | ≤ 1.01 | True |
| ESS bulk min | 866 | ≥ 400 | True |
| ESS tail min | 899 | ≥ 400 | True |
| Divergences | 0 | 0 | True |

Statut : **ok**. 4 chaines, 1000 tirages (1000 de chauffe), target_accept 0.99, 7.0 min d'échantillonnage, 7764 lignes.
IPW : pente sélection 0.995, actif True, ESS/n 0.736, w max 3.65.

## M2 : prior predictive check

| Poste | Médiane | IC50 | IC90 | Dans [30; 150] |
|---|---|---|---|---|
| BACK_ROW | 68.6 | [46.0; 108.5] | [21.8; 215.1] | True |
| CENTRE | 68.6 | [43.5; 112.1] | [24.0; 212.9] | True |
| FLY_HALF | 77.7 | [46.4; 112.8] | [21.8; 217.8] | True |
| FULLBACK | 72.2 | [47.0; 108.7] | [23.3; 194.9] | True |
| HOOKER | 68.3 | [42.3; 113.5] | [20.4; 216.5] | True |
| LOCK | 69.0 | [45.6; 108.2] | [22.5; 220.2] | True |
| PROP | 72.1 | [45.9; 115.9] | [21.9; 235.8] | True |
| SCRUM_HALF | 77.7 | [46.9; 119.9] | [20.8; 229.5] | True |
| WING | 70.9 | [46.5; 104.3] | [22.9; 203.3] | True |

Incidence simulée sous les priors (/1000 h, exposition du train), critère : médiane dans [30; 150] pour chaque poste.

## M2 : effets (moyenne postérieure, IC90 crédible)

| Paramètre | Moyenne [IC90] |
|---|---|
| alpha (intercept, cloglog / match complet) | -3.729 [-4.170; -3.180] |
| sigma_player | 0.719 [0.471; 0.947] |
| sigma_team | 0.102 [0.009; 0.247] |
| beta_load (min_28d standardisé) | 0.060 [-0.001; 0.123] |
| pente consecutive_matches - back_row | -0.028 [-0.322; 0.228] |
| pente consecutive_matches - back_three | 0.010 [-0.229; 0.254] |
| pente consecutive_matches - centre | 0.011 [-0.259; 0.260] |
| pente consecutive_matches - front_row | 0.031 [-0.208; 0.287] |
| pente consecutive_matches - half_back | -0.012 [-0.280; 0.218] |
| pente consecutive_matches - lock | 0.020 [-0.221; 0.287] |
| effet poste - BACK_ROW | -0.428 [-1.088; 0.064] |
| effet poste - CENTRE | -0.179 [-0.795; 0.301] |
| effet poste - FLY_HALF | -0.047 [-0.727; 0.459] |
| effet poste - FULLBACK | -0.245 [-0.913; 0.278] |
| effet poste - HOOKER | -0.570 [-1.231; 0.020] |
| effet poste - LOCK | -0.529 [-1.189; -0.004] |
| effet poste - PROP | -0.617 [-1.256; -0.117] |
| effet poste - SCRUM_HALF | 0.013 [-0.663; 0.537] |
| effet poste - WING | -0.226 [-0.911; 0.245] |
| cr(apps_20min_365d, df=3, constraints='center')[0] | -0.291 [-0.580; 0.005] |
| cr(apps_20min_365d, df=3, constraints='center')[1] | -0.516 [-0.899; -0.168] |
| cr(apps_20min_365d, df=3, constraints='center')[2] | -0.276 [-1.009; 0.440] |
| cr(days_since_last_match_capped, df=3, constraints='center')[0] | -0.320 [-0.650; -0.026] |
| cr(days_since_last_match_capped, df=3, constraints='center')[1] | -0.320 [-0.786; 0.157] |
| cr(days_since_last_match_capped, df=3, constraints='center')[2] | 0.444 [0.159; 0.755] |
| intl_window | -0.266 [-0.606; 0.092] |
| recent_return_8w | -1.119 [-1.686; -0.620] |
| n_prior_injuries_365d | 0.657 [0.552; 0.758] |

Prior beta_load : Normal(0.0363, 0.0416) = log(1,14) par +3,2 FGE / 30 j (Williams 2017) mis à l'échelle de l'écart-type de min_28d au train. Association, pas causalité.

## Courbes h(N) par poste (scénario médian, IC90 crédible)

| Poste | N=0 | N=3 | N=6 | N=9 | N=12 | N=15 | Cumulé 5 |
|---|---|---|---|---|---|---|---|
| BACK_ROW | 0.0155 [0.0093; 0.0235] | 0.0150 [0.0093; 0.0222] | 0.0149 [0.0085; 0.0240] | 0.0152 [0.0067; 0.0293] | 0.0158 [0.0049; 0.0355] | 0.0168 [0.0036; 0.0436] | 0.074 |
| CENTRE | 0.0205 [0.0130; 0.0305] | 0.0207 [0.0134; 0.0308] | 0.0213 [0.0120; 0.0335] | 0.0224 [0.0095; 0.0386] | 0.0241 [0.0076; 0.0492] | 0.0263 [0.0059; 0.0621] | 0.099 |
| FLY_HALF | 0.0239 [0.0151; 0.0365] | 0.0236 [0.0150; 0.0352] | 0.0237 [0.0137; 0.0405] | 0.0243 [0.0110; 0.0473] | 0.0254 [0.0089; 0.0569] | 0.0270 [0.0070; 0.0705] | 0.113 |
| FULLBACK | 0.0186 [0.0113; 0.0273] | 0.0187 [0.0120; 0.0275] | 0.0192 [0.0108; 0.0297] | 0.0200 [0.0091; 0.0354] | 0.0213 [0.0073; 0.0440] | 0.0231 [0.0062; 0.0559] | 0.090 |
| HOOKER | 0.0127 [0.0074; 0.0199] | 0.0130 [0.0077; 0.0203] | 0.0136 [0.0076; 0.0224] | 0.0146 [0.0066; 0.0260] | 0.0159 [0.0056; 0.0326] | 0.0177 [0.0048; 0.0415] | 0.063 |
| LOCK | 0.0169 [0.0100; 0.0255] | 0.0171 [0.0106; 0.0252] | 0.0177 [0.0106; 0.0275] | 0.0188 [0.0091; 0.0345] | 0.0204 [0.0078; 0.0438] | 0.0226 [0.0065; 0.0573] | 0.082 |
| PROP | 0.0124 [0.0072; 0.0192] | 0.0127 [0.0074; 0.0193] | 0.0133 [0.0072; 0.0215] | 0.0142 [0.0060; 0.0256] | 0.0156 [0.0051; 0.0324] | 0.0174 [0.0043; 0.0421] | 0.061 |
| SCRUM_HALF | 0.0250 [0.0160; 0.0373] | 0.0247 [0.0159; 0.0382] | 0.0249 [0.0144; 0.0414] | 0.0256 [0.0117; 0.0498] | 0.0267 [0.0094; 0.0578] | 0.0284 [0.0069; 0.0706] | 0.118 |
| WING | 0.0196 [0.0128; 0.0299] | 0.0197 [0.0129; 0.0297] | 0.0202 [0.0118; 0.0312] | 0.0211 [0.0101; 0.0382] | 0.0225 [0.0085; 0.0488] | 0.0244 [0.0070; 0.0606] | 0.095 |

h(N) = P(blessure au match suivant | N matchs consécutifs), 80 min, profil médian du poste, nouveau joueur et nouvelle équipe-saison (effets intégrés). Moyenne postérieure [IC90 crédible]. Association, pas causalité.

## Risque cumulé sur 5 matchs par scénario

| Poste | median | international_november | return_from_injury | short_turnaround_block |
|---|---|---|---|---|
| BACK_ROW | 0.074 | 0.058 | 0.218 | 0.090 |
| CENTRE | 0.099 | 0.078 | 0.283 | 0.121 |
| FLY_HALF | 0.113 | 0.089 | 0.317 | 0.138 |
| FULLBACK | 0.090 | 0.071 | 0.259 | 0.107 |
| HOOKER | 0.063 | 0.049 | 0.190 | 0.077 |
| LOCK | 0.082 | 0.065 | 0.241 | 0.087 |
| PROP | 0.061 | 0.048 | 0.186 | 0.074 |
| SCRUM_HALF | 0.118 | 0.094 | 0.328 | 0.144 |
| WING | 0.095 | 0.075 | 0.273 | 0.116 |

## Sensibilités (docs/06 §3.3)

| Analyse | Statut | Lignes | Prévalence | Log-loss | Brier skill | Pente | Rapport |
|---|---|---|---|---|---|---|---|
| Référence (m2_hierarchical) | réalisée | 7819 | 0.0171 | 0.0997 | -0.030732529871470814 | -0.035 | `m2_hierarchical-20261108T185750Z.md` |
| Seuil de confiance 0,5 | non réalisable : épisodes < 0,6 non matérialisés dans l'export (relancer dbt avec injury_conf_threshold=0.5) | | | | | | |
| Seuil de confiance 0.8 | non réalisable : confiance max 0.75 < 0.8 dans l'export (relancer dbt avec injury_conf_threshold=0.8) | | | | | | |
| Cible y_injury_any_7d | réalisée (failed) | 7819 | 0.0146 | 0.0862 | +0.0000 | -0.471 | `m2_hierarchical-20261108T191246Z.md` |
| Sans IPW | réalisée (ok) | 7819 | 0.0171 | 0.0957 | +0.0035 | -0.247 | `m2_hierarchical_noipw-20261108T191814Z.md` |
| Sans commotions | non réalisable : type de blessure (commotion) non disponible par épisode dans ml_player_match (docs/10) | | | | | | |
| Exclusion des saisons COVID | non réalisable : aucune saison COVID dans les données | | | | | | |

Les log-loss ne se comparent qu'à cible identique : les variantes de cible (seuil 0,8, any_7d) changent la prévalence.

## Décision

- [ ] Promotion en production (décision humaine, après lecture de ce rapport).

Version enregistrée dans le registre MLflow `rugby-risk-m2` sans promotion.
