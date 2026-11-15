# F13 — Signal « absence » et motifs non-blessure

| Champ | Valeur |
|---|---|
| Phase | 3 |
| Dépendances | F10 |
| Estimation | M |
| Docs de référence | `docs/01-data-sources.md` §4–5, `docs/04-data-model.md` (`fact_eligibility`, `fact_unavailability`) |

## Objectif

Détecter les séquences d'absence (joueur dans l'effectif, pas sur la feuille) et les classer : sélection internationale, suspension, repos protégé, rotation, ou candidate blessure.

## Contexte

Absence ≠ blessure. Ce signal sert à (1) borner la durée des épisodes de blessure (date de retour), (2) éviter de labelliser à tort une absence pour sélection, (3) fournir `absence_reason` au modèle de sélection (F21).

## Périmètre

- [x] Modèle dbt `int_absence_runs` : séquences consécutives de matchs d'équipe sans `on_sheet`, avec début, fin, longueur, match de retour.
- [x] Classification par règles ordonnées (première règle vraie gagne) :
  1. `international_duty` : le joueur figure sur une feuille internationale dans la fenêtre, ou la date est dans une fenêtre de test et le joueur a ≥ 1 sélection sur les 12 derniers mois ;
  2. `suspension` : carton rouge au dernier match joué, absence de 1 à 6 matchs (données disciplinaires détaillées hors périmètre, règle heuristique documentée) ;
  3. `protected_rest` : joueur dans `protected_players.csv` de la saison, absence d'un seul match ;
  4. `injury_candidate` : absence ≥ 2 matchs d'équipe consécutifs hors fenêtre internationale, **ou** précédée d'un signal de sortie F12 ≥ 0,5 ;
  5. `rotation` : absence d'un seul match sans autre indice ;
  6. `unknown`.
- [x] Mise à jour de `fact_eligibility.absence_reason` (via un modèle aval, pas d'écriture dans les sources) et alimentation de `fact_unavailability` pour les raisons non-blessure.
- [x] Rapport : répartition des motifs par saison et poste.

## Hors périmètre

- Scraping des décisions de la commission de discipline (amélioration future, noter dans le journal si jugé prioritaire).

## Spécification technique

Paramètres dans `config/injury_rules.yaml` (section `absence_signal`) : `min_matches_injury_candidate: 2`, `suspension_max_matches: 6`, `protected_rest_max_matches: 1`, `exit_link_threshold: 0.5`.

Fin de saison : une absence qui court jusqu'à la fin de saison est marquée `censored_end_of_season = true`.

## Fichiers

| Fichier | Action |
|---|---|
| `dbt/models/intermediate/int_absence_runs.sql`, `int_eligibility__with_reason.sql` + `.yml` | créer |
| `dbt/models/marts/fact_unavailability.sql` + `.yml` | créer |
| `config/injury_rules.yaml` | modifier |

## Tests

- `tests/integration/injuries/test_absence_signal.py` — cas synthétiques : absence pendant le Six Nations d'un international (international_duty), absence d'un match après un rouge (suspension), absence de 4 matchs hors fenêtre (injury_candidate), absence d'un match d'un joueur protégé (protected_rest), absence d'un match isolée (rotation), absence jusqu'à la fin de saison (censurée).

## Critères d'acceptation

- [x] Les 6 cas synthétiques sont correctement classés.
- [x] Aucune absence d'international pendant une fenêtre de test n'est classée `injury_candidate` sans signal de sortie.
- [x] `make check` vert.

## Journal

- 2026-11-05 — Livré sur branche `feat/F13-signal-absences`.
  - « International » = feuille d'une équipe nationale (`dim_team.is_national`) pendant la
    fenêtre de la période d'absence, ou fenêtre atteinte et ≥ 1 sélection dans les
    `intl_history_days` (365) précédents (`absence_signal` dans `config/injury_rules.yaml`).
  - **Correspondance `protected_players` par nom** (`lower` + retrait espaces/tirets) : le CSV
    de référence est nominatif, sans identifiant joueur. Limitation acceptée (listes
    protégées = dizaines de joueurs saison, saisie manuelle) ; à fiabiliser si besoin.
  - Suspension : carte rouge au **dernier match joué avant l'absence** (correction en cours
    de test : la jointure initiale visait le dernier match *absent*). Heuristique 1–6 matchs
    documentée ; scraping de la commission de discipline noté hors périmètre (non jugé
    prioritaire : les décisions détaillées arrivent souvent après plusieurs matchs et la
    règle heuristique couvre le cas dominant).
  - `fact_eligibility.absence_reason` n'est pas écrit : l'enrichissement vit dans
    `int_eligibility__with_reason` (même convention que F12, sources non écrasées).
  - `injury_candidate` **n'entre pas** dans `fact_unavailability` (ce n'est pas une
    indisponibilité confirmée) ; la censure de fin de saison y est portée
    (`censored_end_of_season`).
  - Seed `ref_protected_players` : types de colonnes déclarés dans `dbt/seeds/schema.yml`
    (CSV vide → entier inféré sinon).
  - Rapport `reports/absence_reasons.md` via `uv run rugby-risk report absences` (k ≥ 10).

