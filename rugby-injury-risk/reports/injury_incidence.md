# Incidence reconstruite vs priors (docs/02 §2)

Plage attendue : 40-110 blessures en match / 1000 h.

## Toutes les blessures en match détectées (contrôle de détection)

| Saison | Groupe de poste | Blessures | Heures | /1000 h |
|---|---|---|---|---|
| 2022-2023 | back_row | 49 | 1455 | 33.7 |
| 2022-2023 | back_three | 72 | 1494 | 48.2 |
| 2022-2023 | centre | 72 | 971 | 74.1 |
| 2022-2023 | front_row | 43 | 1486 | 28.9 |
| 2022-2023 | half_back | 109 | 1004 | 108.6 |
| 2022-2023 | lock | 41 | 981 | 41.8 |
| 2023-2024 | back_row | 61 | 1460 | 41.8 |
| 2023-2024 | back_three | 65 | 1450 | 44.8 |
| 2023-2024 | centre | 63 | 986 | 63.9 |
| 2023-2024 | front_row | 41 | 1473 | 27.8 |
| 2023-2024 | half_back | 127 | 1051 | 120.9 |
| 2023-2024 | lock | 30 | 1009 | 29.7 |
| 2024-2025 | back_row | 58 | 1528 | 37.9 |
| 2024-2025 | back_three | 88 | 1457 | 60.4 |
| 2024-2025 | centre | 68 | 1004 | 67.7 |
| 2024-2025 | front_row | 46 | 1500 | 30.7 |
| 2024-2025 | half_back | 124 | 1004 | 123.5 |
| 2024-2025 | lock | 43 | 963 | 44.7 |

Cellules hors plage : 8 (asset check WARN)

## Label ML `y_injury` (confiance >= 0.6)

Cible réellement modélisée (F17-F22). Les sorties précoces sans absence ultérieure
(score « sortie seule » sous le seuil) en sont exclues : la cible sous-déclare les
blessures courtes par construction. Résultats conditionnels à cette définition.

| Saison | Groupe de poste | Blessures | Heures | /1000 h |
|---|---|---|---|---|
| 2022-2023 | back_row | 25 | 1455 | 17.2 |
| 2022-2023 | back_three | 27 | 1494 | 18.1 |
| 2022-2023 | centre | 26 | 971 | 26.8 |
| 2022-2023 | front_row | 16 | 1486 | 10.8 |
| 2022-2023 | half_back | 30 | 1004 | 29.9 |
| 2022-2023 | lock | 18 | 981 | 18.4 |
| 2023-2024 | back_row | 26 | 1460 | 17.8 |
| 2023-2024 | back_three | 27 | 1450 | 18.6 |
| 2023-2024 | centre | 17 | 986 | 17.2 |
| 2023-2024 | front_row | 15 | 1473 | 10.2 |
| 2023-2024 | half_back | 24 | 1051 | 22.8 |
| 2023-2024 | lock | 8 | 1009 | 7.9 |
| 2024-2025 | back_row | 24 | 1528 | 15.7 |
| 2024-2025 | back_three | 35 | 1457 | 24.0 |
| 2024-2025 | centre | 28 | 1004 | 27.9 |
| 2024-2025 | front_row | 14 | 1500 | 9.3 |
| 2024-2025 | half_back | 21 | 1004 | 20.9 |
| 2024-2025 | lock | 14 | 963 | 14.5 |

Incidence poolée : toutes = 53.9 / 1000 h ; label ML = 17.7 / 1000 h.
