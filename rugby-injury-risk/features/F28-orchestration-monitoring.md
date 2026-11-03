# F28 — Orchestration complète et monitoring

| Champ | Valeur |
|---|---|
| Phase | 8 |
| Dépendances | F10, F25 |
| Estimation | M |
| Docs de référence | `docs/03-architecture.md` §2.9, §3, `docs/06-modeling.md` §6 |

## Objectif

Assembler tous les assets en jobs planifiés (hebdomadaire après chaque journée, reconstruction, publication), et surveiller la qualité des données, la dérive des features et la calibration.

## Contexte

En saison, le pipeline doit tourner chaque semaine sans intervention, et alerter quand une source change de format, quand la labellisation dérive ou quand le modèle se décalibre.

## Périmètre

- [ ] `orchestration/jobs.py` :
  - `ingest_weekly` : partitions de la journée courante pour toutes les sources autorisées (les non autorisées sont sautées avec un log, pas une erreur) ;
  - `rebuild_warehouse` : `dbt build` complet ;
  - `publish` : `public_predictions` avec le modèle promu ;
  - `train_season` : manuel uniquement.
- [ ] `orchestration/schedules.py` : `ingest_weekly` le lundi 06:00 Europe/Paris, puis `rebuild_warehouse` et `publish` enchaînés par sensors de succès.
- [ ] Asset checks de monitoring (`orchestration/checks.py`) :
  - qualité scraping : taux de pages en quarantaine par source et par semaine (> 5 % → WARN, > 20 % → ERROR) ;
  - couverture : matchs de la journée attendus (calendrier) vs ingérés ;
  - labellisation : incidence reconstruite glissante vs plage de priors ;
  - dérive des features : PSI de `min_28d`, `consecutive_matches`, `days_since_last_match` vs saison d'entraînement (PSI > 0,2 → WARN) ;
  - calibration glissante de fin de saison (pas hebdomadaire, trop peu d'événements).
- [ ] Notifications : log structuré + option webhook (Slack/Discord) configurable par `ALERT_WEBHOOK_URL`, désactivée par défaut.
- [ ] `reports/weekly_ops.md` généré à chaque run : sources, volumes, alertes.

## Hors périmètre

- Déploiement cloud de Dagster (local ou serveur unique pour le MVP ; piste Dagster+ notée dans le journal).

## Fichiers

| Fichier | Action |
|---|---|
| `orchestration/{jobs,schedules,sensors,checks}.py` | créer |
| `src/rugby_risk/monitoring/{__init__,psi,alerts}.py` | créer |

## Tests

- `tests/unit/monitoring/test_psi.py` — PSI de distributions connues.
- `tests/unit/orchestration/test_definitions.py` — `Definitions` se chargent, tous les assets ont une partition cohérente, schedules valides.
- `tests/integration/orchestration/test_weekly_offline.py` — exécution de `ingest_weekly` sur une journée de fixtures en mode offline, sources non autorisées sautées.

## Critères d'acceptation

- [ ] `make dagster` affiche tous les jobs, schedules et checks.
- [ ] Run hebdomadaire complet en offline sur fixtures sans erreur.
- [ ] `make check` vert.

## Journal

