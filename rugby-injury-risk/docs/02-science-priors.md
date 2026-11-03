# 02 — État de la science et priors

Ce document fixe les **ordres de grandeur de référence** utilisés pour : (1) valider la labellisation des blessures, (2) informer les priors du modèle bayésien, (3) interpréter les résultats.

## 1. Chiffres de référence

| Indicateur | Valeur | Source |
|---|---|---|
| Incidence blessures en match, Premiership | 76/1000 h (2022-23) ; moyenne 2002-22 : 86/1000 h ; 1,5 blessure/équipe/match | PRISP 2022-23 |
| Gravité moyenne / médiane | 38 j / 17 j (médiane 2002-22 : 10 j) | PRISP 2022-23 |
| Burden | 2 879 jours d'absence/1000 h | PRISP 2022-23 |
| Commotion en match | 18,4/1000 h ; 24 % des blessures de match ; 18 j d'absence moyenne | PRISP 2022-23 |
| Entraînement | 3,2/1000 h ; 37 % des blessures | PRISP 2022-23 |
| Plaquage | 50 % des blessures de match | PRISP 2022-23 |
| Synthétique vs naturel | Sur dix saisons : 84 vs 81/1000 h (pas de différence d'incidence) ; gravité +6 j sur synthétique (39 vs 33 j) | PRISP 2022-23 |
| Commotion Top 14 (2014-2018) | 10,4/1000 h (IC 9,3–11,5) ; demis 16,1 ; phases finales IRR 3,96 | Chéradame et al., Am J Sports Med 2021 |
| Sorties définitives Top 14 (2012-13 → 2014-15) | 2 208 sorties ; première ligne 26 % ; première ligne + demis 43 % | Étude médicale LNR/FFR (relayée par la presse, non publiée en revue) |
| Coupe du monde 2015 | 90,1/1000 h (arrières 100,4 ; avants 81,1) ; gravité 29,8 j | Fuller et al., BJSM 2017 |
| Par poste (Premiership 2002-04) | Talonneur 114/1000 h, poste le plus exposé avec le centre extérieur | Brooks et al., BJSM 2005 |
| Avants vs arrières (méta-analyse 2025) | IRR ≈ 1,03 (IC 1,00–1,06) ; avants ~2× plus de blessures tronc/dos | Méta-analyse 2025 |
| Après commotion | +60 % de risque de blessure ultérieure | Cross et al., BJSM 2016 |

## 2. Conversion en probabilité par match

Avec un taux λ (blessures/heure) et une exposition E (heures), `P = 1 − exp(−λ·E)`.

| Cas | λ | E | P par match complet |
|---|---|---|---|
| Moyenne Premiership | 0,076 | 1,33 h | ≈ 9,6 % |
| Talonneur | 0,114 | 1,33 h | ≈ 14 % |
| Commotion seule | 0,0184 | 1,33 h | ≈ 2,4 % |

**Attendu pour ce projet** : avec la sous-déclaration des données publiques, un taux de base de l'ordre de **5 à 8 % par match complet**. L'écart entre l'incidence reconstruite et ces priors mesure la qualité de la labellisation (contrôle automatique en F16).

Ces constantes sont centralisées dans `src/rugby_risk/modeling/priors.py` (F19) et ne doivent pas être recopiées ailleurs.

## 3. Charge de matchs et risque

- **Williams et al., Sports Medicine 2017** (1 253 joueurs, 7 saisons de Premiership, modèle de fragilité emboîté joueur ⊂ équipe) :
  - exposition sur 12 mois (matchs ≥ 20 min) **non linéaire** : risque accru sous ~15 et au-dessus de ~35 matchs ;
  - exposition sur 1 mois **linéaire** : HR 1,14 pour +3,2 équivalents-matchs complets (IC 90 % 1,08–1,20) ;
  - effet atténué chez les joueurs à forte charge chronique (> 28 matchs sur 12 mois) ;
  - +6 blessures antérieures : HR 1,28 (IC 90 % 1,15–1,41).
- **Williams et al., J Sci Med Sport 2023** : ≥ 31 matchs dans une saison sont associés à un burden accru la saison suivante (pas à l'incidence). Modéliser **incidence et gravité séparément**.
- **Chéradame et al. 2021 (Top 14)** : plus de temps de jeu cumulé associé à **moins** de commotions → effet « survivant en bonne santé ».
- **Repos** : World Rugby recommande au moins **4 jours pleins** entre deux matchs → feature `short_turnaround`.

## 4. ACWR : ne pas l'utiliser

Impellizzeri et al. (IJSPP 2020) et Lolli et al. (BJSM 2019) : couplage mathématique, zone « idéale » 0,8–1,3 artefactuelle, un ACWR avec charge chronique aléatoire prédit aussi bien. On entre **charges aiguës et chroniques séparément**, éventuellement en EWMA, et on laisse le modèle estimer l'interaction.

## 5. Ce que la prédiction ML peut atteindre

| Étude | Données | Performance |
|---|---|---|
| Leckey et al., Sports Med Open 2026 (129 joueurs, provinces irlandaises + XV d'Irlande) | GNSS, wellness, screening, historique | ROC AUC 0,66 ; précision 1,3 % — pas d'aide à la décision |
| Ren et al., Eur J Sport Sci 2025 (63 joueurs, 1 club) | GPS, ACWR | AUC jusqu'à 0,82, petit échantillon → sur-apprentissage probable |
| Revue de portée ML injury, BJSM 2025 (38 études) | Variées | AUC 0,57–0,95 ; les AUC > 0,9 sont des signaux d'alerte |
| Carey et al. (AFL) | Charges | AUC 0,52 d'une saison à l'autre |

**Conséquence** : ce projet vise la **calibration par poste**. Une AUC supérieure à 0,75 sur données publiques doit déclencher une recherche de fuite de données.

## 6. Critiques fondamentales à garder en tête

- **Bahr (BJSM 2016)** : association ≠ prédiction ≠ bénéfice d'une intervention.
- **Paradoxe de la gestion de charge** : les joueurs fatigués sont mis au repos avant de se blesser ; la sélection biaise les associations. Correction par IPW (F21).
- **Non-stationnarité** : protocoles commotion, conventions FFR/LNR, formats internationaux évoluent → features de période, réentraînement annuel.

## 7. Recommandations méthodologiques retenues

- Cadre temps-jusqu'à-l'événement avec covariables dépendantes du temps et événements récurrents (Nielsen et al., BJSM 2019), implémenté en **temps discret** (logistique joueur-match).
- Hiérarchie joueur ⊂ poste ⊂ groupe, plus équipe-saison.
- Pas de SMOTE (casse la calibration). Prévalences réelles, évaluation par log-loss, Brier, calibration, PR-AUC.
- Validation par saison (rolling origin), jamais de k-fold aléatoire.

## 8. Références principales

- PRISP 2022-23 Report — keepyourbootson.co.uk
- Chéradame J. et al., Am J Sports Med 2021 — doi:10.1177/03635465211006480
- Williams S. et al., Sports Med 2017 — PMC5633632
- Williams S. et al., J Sci Med Sport 2023
- Brooks J. et al., BJSM 2005
- Fuller C. et al., BJSM 2017 (RWC 2015)
- Cross M. et al., BJSM 2016
- Impellizzeri F. et al., IJSPP 2020 ; Lolli L. et al., BJSM 2019
- Leckey C. et al., Sports Med Open 2026 — doi:10.1186/s40798-026-01060-7
- Bahr R., BJSM 2016
- Nielsen R. et al., BJSM 2019 (time-to-event, parties 1 et 2)
- World Rugby, Recommended rest between matches
