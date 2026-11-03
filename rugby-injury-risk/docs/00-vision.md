# 00 — Vision du projet

## Le problème

Les joueurs professionnels de Top 14 enchaînent championnat, coupes d'Europe et matchs internationaux. Fin octobre 2026, environ un joueur sur cinq du Top 14 est indisponible. Staffs, médias et instances se posent la même question : **à partir de combien de matchs consécutifs le risque de blessure augmente-t-il, et est-ce différent pour un pilier et pour un ailier ?**

## La question précise

> Pour un joueur de poste P, ayant joué N matchs consécutifs, avec un profil de charge passée C et des antécédents A, quelle est la probabilité qu'il se blesse lors de son prochain match ?

Formellement : on estime un **hazard en temps discret**

```
h(t) = P(blessure au match t | aucune blessure en cours avant t, X(t⁻))
```

où `X(t⁻)` regroupe les features connues avant le coup d'envoi du match `t`.

La probabilité cumulée de blessure sur une séquence de K matchs est `1 − ∏ (1 − h_k)`.

## Livrables

| # | Livrable | Feature(s) |
|---|---|---|
| L1 | Entrepôt de participation Top 14 + internationaux + coupes d'Europe, 2013/14 → saison en cours | F03–F10 |
| L2 | Analyse descriptive des séquences de matchs consécutifs par poste (publiable sans données de blessure) | F11 |
| L3 | Base d'épisodes de blessure reconstruits avec score de confiance, précision mesurée | F12–F16 |
| L4 | Table d'apprentissage joueur-match sans fuite temporelle | F17 |
| L5 | Modèles calibrés : baseline, hazard logistique, hiérarchique bayésien, GBM, gravité | F19–F24 |
| L6 | API + tableau de bord agrégé par poste | F25–F27 |
| L7 | Monitoring, réentraînement annuel, model card, data card, AIPD | F28–F29 |

## Critères de succès

**Données**
- 100 % des matchs de Top 14 des saisons couvertes présents ; contrôle « somme des minutes par équipe ≈ 15 × 80 » passé sur plus de 98 % des matchs.
- Moins de 1 % de joueurs dupliqués sur un échantillon audité après résolution d'entités.
- Précision de la labellisation blessure ≥ 0,85 sur 300 à 500 épisodes annotés à la main.
- Incidence reconstruite par saison dans une plage plausible au regard des priors : 50 à 90 blessures/1000 h de match, sachant qu'on attend une sous-déclaration (voir `02-science-priors.md`).

**Modèles**
- Brier skill score > 0 face à la baseline par poste sur au moins 3 saisons de test.
- Pente de calibration entre 0,8 et 1,2 par groupe de postes.
- Courbes h(N) par poste avec intervalles crédibles à 90 %, stables d'une saison de test à l'autre.

**Produit**
- Tableau de bord public sans aucune donnée de santé nominative.
- Page méthodologie qui explique limites, biais et calibration.

## Non-objectifs

- Prédire individuellement qui va se blesser.
- Affirmer une causalité charge → blessure.
- Remplacer l'avis d'un staff médical.

## Utilisateurs cibles

- **Analystes et journalistes data** : comprendre les ordres de grandeur par poste.
- **Staffs** (à terme, avec leurs propres données internes) : réutiliser le cadre méthodologique.
- **Le porteur du projet** : portfolio data science sport, base pour un partenariat avec la LNR (accès à l'enquête médicale obligatoire).
