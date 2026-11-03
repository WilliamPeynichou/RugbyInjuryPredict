# 09 — Glossaire

## Rugby

| Terme | Définition |
|---|---|
| Top 14 | Première division professionnelle française (14 clubs, 26 journées + phases finales) |
| Pro D2 | Deuxième division professionnelle |
| Champions Cup / Challenge Cup | Coupes d'Europe des clubs (EPCR) |
| Feuille de match | Liste officielle des 23 joueurs : 15 titulaires (n° 1–15) et 8 remplaçants (n° 16–23) |
| Première ligne | Piliers (1, 3) et talonneur (2) |
| Deuxième ligne | n° 4 et 5 |
| Troisième ligne | Flankers (6, 7) et n° 8 |
| Charnière / demis | Demi de mêlée (9) et demi d'ouverture (10) |
| Trois-quarts centres | n° 12 et 13 |
| Triangle arrière | Ailiers (11, 14) et arrière (15) |
| JIFF | Joueur issu des filières de formation (statut réglementaire LNR) |
| HIA | Head Injury Assessment, protocole d'évaluation des commotions |
| Convention FFR/LNR | Accord encadrant la mise à disposition et la protection des internationaux français |
| Liste des joueurs protégés | Internationaux soumis à des limites de temps de jeu (33 depuis juillet 2026) |
| Fenêtre internationale | Période de tests (Six Nations, tests de novembre, tournée d'été) |
| Doublon | Match de club joué pendant une fenêtre internationale |

## Épidémiologie

| Terme | Définition |
|---|---|
| Incidence | Nombre de blessures pour 1000 heures d'exposition |
| Gravité (severity) | Jours d'absence jusqu'au retour à la disponibilité complète |
| Burden | Incidence × gravité moyenne = jours d'absence pour 1000 h |
| Time-loss injury | Blessure entraînant au moins un jour d'indisponibilité (consensus World Rugby : > 24 h) |
| Classes de gravité | Minime/légère 2–7 j, modérée 8–28 j, sévère > 28 j |
| PRISP | Professional Rugby Injury Surveillance Project (Angleterre) |
| ACWR | Acute:Chronic Workload Ratio — ratio non utilisé dans ce projet |
| FGE | Full-game equivalent, équivalent-match complet (80 minutes) |
| Effet survivant en bonne santé | Les joueurs qui jouent beaucoup sont ceux qui ne se blessent pas, d'où une association trompeuse « jouer protège » |

## Données et modélisation

| Terme | Définition |
|---|---|
| Lac brut | Stockage immuable des réponses HTTP avant parsing |
| Staging | Données parsées, typées, par source |
| Marts | Tables finales (dimensions et faits) |
| Résolution d'entités | Rapprocher les fiches d'un même joueur entre sources |
| Éligibilité | Un joueur est éligible à un match si son équipe le joue pendant qu'il est dans l'effectif |
| as_of_ts | Instant de référence avant lequel toutes les informations utilisées doivent être connues |
| Fuite de données (leakage) | Utilisation involontaire d'une information postérieure à l'instant de prédiction |
| Hazard en temps discret | Probabilité d'événement à un pas de temps, conditionnelle à l'absence d'événement avant |
| cloglog | Lien complementary log-log, cohérent avec un taux de Poisson |
| Offset | Terme connu (log de l'exposition) ajouté au prédicteur linéaire sans coefficient |
| IPW | Inverse Probability Weighting, pondération par l'inverse de la probabilité d'être observé |
| Fragilité (frailty) | Effet aléatoire individuel capturant une propension propre à se blesser |
| Rolling origin | Validation où l'on avance l'origine temporelle d'entraînement saison par saison |
| Brier score | Erreur quadratique moyenne d'une probabilité ; Brier skill score = 1 − Brier/Brier_ref |
| Pente de calibration | Coefficient de la régression de y sur logit(p̂) ; 1 = parfaitement calibré |
| k-anonymat | Toute cellule publiée agrège au moins k individus (k = 10 ici) |
