# F11 — Analyse descriptive des séquences par poste

| Champ | Valeur |
|---|---|
| Phase | 2 |
| Dépendances | F10 |
| Estimation | M |
| Docs de référence | `docs/00-vision.md` (L2), `docs/05-features-spec.md` §1–2 |

## Objectif

Produire une première analyse **publiable sans aucune donnée de blessure** : distribution réelle des séquences de matchs consécutifs et de la charge par poste en Top 14, et leur évolution avec les conventions FFR/LNR.

## Contexte

Elle valide les marts de participation, fournit des ordres de grandeur pour le choix des splines (F20) et constitue un premier livrable portfolio.

## Périmètre

- [ ] Modèle dbt `analysis_player_sequences` : une ligne par séquence (joueur, début, fin, longueur, minutes totales, compétitions traversées, raison de fin : absence / banc non entré / fin de saison).
- [ ] Module `src/rugby_risk/analysis/sequences.py` : agrégats par `position_code` et saison (médiane, P90, max de longueur de séquence ; minutes par saison ; part des titulaires ≥ 60 min ; nombre de rotations courtes).
- [ ] Figures (matplotlib, style sobre) : distribution des longueurs par poste, évolution par saison, effet des périodes réglementaires (`season_period`).
- [ ] Rapport `reports/descriptive_sequences.md` généré par `uv run rugby-risk report sequences`, uniquement agrégé (k ≥ 10 joueurs par cellule).
- [ ] Notebook d'exploration facultatif dans `notebooks/` (non importé par `src/`).

## Hors périmètre

- Toute donnée de blessure.

## Spécification technique

Définition de séquence identique à `consecutive_matches` (`docs/05-features-spec.md` §2) : la même fonction Python ou macro dbt sera réutilisée en F17. **Écrire la logique une seule fois** (macro dbt `consecutive_run_id`) et l'utiliser ici.

## Fichiers

| Fichier | Action |
|---|---|
| `dbt/macros/consecutive_run_id.sql` | créer |
| `dbt/models/analysis/analysis_player_sequences.sql` | créer |
| `src/rugby_risk/analysis/{__init__,sequences,figures}.py` | créer |
| `reports/descriptive_sequences.md` (généré) | créer |

## Tests

- `tests/unit/analysis/test_sequences.py` — sur un joueur synthétique (J1–J5 joués, J6 banc non entré, J7–J9 joués) : deux séquences de longueur 5 et 3.
- `tests/unit/analysis/test_k_anonymity.py` — une cellule < 10 joueurs est supprimée du rapport.

## Critères d'acceptation

- [ ] Rapport généré sans erreur sur les données disponibles.
- [ ] La macro `consecutive_run_id` est la seule implémentation des séquences dans le dépôt.
- [ ] `make check` vert.

## Journal

