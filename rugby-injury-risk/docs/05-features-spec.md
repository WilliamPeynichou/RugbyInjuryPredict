# 05 — Spécification des features

Toutes les features de `ml_player_match` sont calculées **as of** `as_of_ts = kickoff_ts − 1 s`, à partir d'événements dont l'horodatage est strictement antérieur. Implémentation : modèles dbt `dbt/models/ml/` (F17), helpers Python dans `src/rugby_risk/features/` si une logique n'est pas exprimable proprement en SQL.

Notations : `t` = match courant du joueur (éligible), `D` = date du coup d'envoi. « Match » inclut toutes compétitions (club + international) sauf mention.

## 1. Charge de matchs

| Feature | Type | Définition |
|---|---|---|
| `min_7d`, `min_14d`, `min_28d`, `min_56d`, `min_365d` | int | Somme des minutes jouées dans `[D − k jours, D)` |
| `min_intl_56d` | int | Idem, compétitions `level = international` |
| `min_club_28d` | int | Idem, `level ∈ {club_domestic, club_europe}` |
| `apps_20min_365d` | int | Nombre de matchs avec ≥ 20 minutes sur 365 j (définition Williams / FFR) |
| `fge_30d` | float | Équivalents-matchs complets sur 30 j = minutes / 80 |
| `ewma_acute`, `ewma_chronic` | float | EWMA des minutes par match, demi-vies 7 j et 28 j (calcul journalier, minutes = 0 les jours sans match) |
| `season_minutes` | int | Minutes depuis `dim_season.start_date` |
| `season_round_index` | int | Rang du match dans la saison du club |

**Interdit** : tout ratio aiguë/chronique (ACWR).

## 2. Enchaînement

| Feature | Type | Définition |
|---|---|---|
| `consecutive_matches` | int | Nombre de matchs consécutifs **de l'équipe du joueur** (club ou sélection selon le calendrier qu'il suit) où il a joué ≥ 1 minute, en remontant depuis le match précédent `t`. Remis à 0 dès qu'un match d'équipe est manqué. |
| `consecutive_starts` | int | Même logique, uniquement les titularisations |
| `consecutive_heavy` | int | Même logique, matchs ≥ 60 minutes |
| `days_since_last_match` | int | Jours entre le dernier match joué et `D` (NULL → 999 + flag) |
| `short_turnaround` | bool | `days_since_last_match < 5` (moins de 4 jours pleins de repos) |
| `n_short_turnarounds_28d` | int | Nombre de rotations < 5 jours sur 28 j |
| `weeks_without_rest` | int | Semaines consécutives avec au moins un match joué |

Cas particuliers de `consecutive_matches` :
- Un joueur en sélection : la séquence suit les matchs qu'il pouvait jouer (club puis sélection). Implémentation : la « séquence d'équipe » est l'union ordonnée des matchs `fact_eligibility` du joueur (club + sélection).
- Un banc non entré (`on_sheet` et `minutes_played = 0`) **casse** la séquence de `consecutive_matches` mais pas `weeks_without_rest`.

## 3. International et protection

| Feature | Type | Définition |
|---|---|---|
| `intl_window` | bool | `D` dans une fenêtre de `test_windows.csv` |
| `days_since_last_test` | int | Jours depuis le dernier match international joué (999 si aucun) |
| `intl_caps_365d` | int | Matchs internationaux joués sur 365 j |
| `protected_list` | bool | Joueur présent dans `protected_players.csv` pour la saison |
| `protection_regime` | cat | Régime de `rules_protection.csv` applicable à la date |

## 4. Antécédents de blessure

Calculés uniquement avec des épisodes dont `onset_date < D` **et** connus avant `D`, et avec `source_confidence ≥ INJURY_CONF_THRESHOLD` (défaut 0,6, paramétrable).

| Feature | Type | Définition |
|---|---|---|
| `n_prior_injuries_365d` | int | Épisodes sur 365 j |
| `n_prior_injuries_career` | int | Épisodes depuis le début de la fenêtre observée |
| `days_missed_365d` | int | Somme des jours manqués sur 365 j (épisodes clos avant `D`) |
| `days_since_last_injury` | int | Jours depuis `onset_date` du dernier épisode (999 si aucun) |
| `days_since_return` | int | Jours depuis le dernier `return_date` (999 si aucun) |
| `recent_return_8w` | bool | `days_since_return ≤ 56` |
| `prior_concussions_365d` | int | Commotions sur 365 j |
| `observed_history_days` | int | Jours d'historique disponibles pour le joueur (contrôle de censure à gauche) |

## 5. Individu

| Feature | Type | Définition |
|---|---|---|
| `age` | float | Années à `D` |
| `height_cm`, `weight_kg` | int | Profil (imputation par médiane du poste + flag si manquant) |
| `bmi_rel_position` | float | IMC − médiane IMC du poste |
| `pro_seasons` | int | Saisons observées avec ≥ 1 match pro avant la saison courante |

## 6. Contexte du match

| Feature | Type | Définition |
|---|---|---|
| `is_home` | bool | Équipe du joueur à domicile |
| `surface` | cat | `natural / hybrid / synthetic / unknown` via `venue_surface` |
| `travel_km_14d` | float | Distance orthodromique cumulée des déplacements sur 14 j |
| `is_playoff` | bool | Phase finale |
| `competition_code` | cat | Compétition du match `t` |
| `month` | int | Mois de `D` |
| `opponent_strength` | float | Classement de l'adversaire **avant** le match (points / match à `D`) |
| `season_period` | cat | Période réglementaire (avant 2017, 2017-2018, 2018-2026, depuis juillet 2026) |

**Interdit** : score final, écart au score, cartons du match `t`, minutes du match `t`.

## 7. Cibles

| Colonne | Définition |
|---|---|
| `y_injury` | Il existe un `fact_injury_event` avec `context = match`, `onset_match_id = t`, `source_confidence ≥ threshold` |
| `y_injury_any_7d` | (Variante) épisode quel que soit le contexte avec `onset_date ∈ [D, D+7)` |
| `y_days_missed` | `days_missed` de l'épisode (pour F24) |
| `y_injury_conf` | Confiance de l'épisode |

Le seuil et la variante de cible sont des paramètres d'expérience loggés dans MLflow.

## 8. Contrôle de fuite (F17)

Test automatique : pour un échantillon de 1 000 lignes, recalculer chaque feature en ne chargeant **que** les événements avec horodatage `< as_of_ts` et vérifier l'égalité exacte. Plus un test de permutation : décaler les cibles d'un match doit faire chuter la performance au niveau de la baseline.
