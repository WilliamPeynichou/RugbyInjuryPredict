# ROADMAP — features ordonnées

Règle : Claude Code prend la **première feature `todo` dont toutes les dépendances sont `done`**. Statuts possibles : `todo`, `in_progress`, `done`, `blocked` (avec raison dans le journal de la fiche).

Estimation : S ≤ ½ jour · M 1–2 jours · L 3–5 jours.

## Phase 0 — Socle et cadrage

| ID | Feature | Dépend de | Est. | Statut |
|---|---|---|---|---|
| F00 | [Bootstrap du dépôt](F00-bootstrap.md) | — | M | done |
| F01 | [Registre des sources et configuration](F01-config-sources.md) | F00 | S | done |
| F02 | [Données de référence](F02-reference-data.md) | F00 | M | done |

## Phase 1 — Collecte et entrepôt Top 14

| ID | Feature | Dépend de | Est. | Statut |
|---|---|---|---|---|
| F03 | [Client HTTP poli et lac brut](F03-http-raw-store.md) | F01 | M | done |
| F04 | [Entrepôt DuckDB et projet dbt](F04-warehouse-dbt.md) | F02 | M | done |
| F05 | [Ingestion allrugby (minutes et profils)](F05-ingest-allrugby.md) | F03, F04 | L | done |
| F06 | [Ingestion LNR (feuilles de match)](F06-ingest-lnr.md) | F03, F04 | M | done |

## Phase 2 — Internationaux, coupes d'Europe, résolution d'entités

| ID | Feature | Dépend de | Est. | Statut |
|---|---|---|---|---|
| F07 | [Ingestion des matchs internationaux](F07-ingest-internationals.md) | F03, F04 | M | done |
| F08 | [Ingestion coupes d'Europe et calendrier](F08-ingest-europe-calendar.md) | F03, F04 | M | done |
| F09 | [Résolution d'entités joueurs](F09-entity-resolution.md) | F05, F06, F07 | L | done |
| F10 | [Marts de participation et éligibilité](F10-participation-marts.md) | F08, F09 | L | done |
| F11 | [Analyse descriptive des séquences par poste](F11-descriptive-sequences.md) | F10 | M | done |

## Phase 3 — Labellisation des blessures

| ID | Feature | Dépend de | Est. | Statut |
|---|---|---|---|---|
| F12 | [Signal « sortie précoce »](F12-signal-exits.md) | F10 | M | done |
| F13 | [Signal « absence » et motifs non-blessure](F13-signal-absences.md) | F10 | M | done |
| F14 | [Collecte presse et points médicaux](F14-ingest-news.md) | F03, F04 | M | done |
| F15 | [Extraction LLM des blessures](F15-llm-injury-extraction.md) | F14, F09 | L | done |
| F16 | [Fusion des signaux, annotation et contrôle qualité](F16-injury-fusion-annotation.md) | F12, F13, F15 | L | done |

## Phase 4 — Table d'apprentissage et baselines

| ID | Feature | Dépend de | Est. | Statut |
|---|---|---|---|---|
| F17 | [Table ml_player_match et test anti-fuite](F17-ml-table-leakage.md) | F16 | L | done |
| F18 | [Cadre d'évaluation temporelle et MLflow](F18-evaluation-framework.md) | F17 | M | done |
| F19 | [Baseline Poisson par poste et priors](F19-baseline-poisson.md) | F18 | S | todo |
| F20 | [Hazard en temps discret](F20-discrete-hazard.md) | F19 | M | todo |

## Phase 5 — Modèle de production

| ID | Feature | Dépend de | Est. | Statut |
|---|---|---|---|---|
| F21 | [Modèle de sélection et pondération IPW](F21-selection-ipw.md) | F20 | M | todo |
| F22 | [Modèle hiérarchique bayésien par poste](F22-hierarchical-bayes.md) | F21 | L | todo |

## Phase 6 — Challenger et gravité

| ID | Feature | Dépend de | Est. | Statut |
|---|---|---|---|---|
| F23 | [Challenger gradient boosting et SHAP](F23-gbm-challenger.md) | F20 | M | todo |
| F24 | [Modèle de gravité](F24-severity.md) | F18 | M | todo |

## Phase 7 — Produit

| ID | Feature | Dépend de | Est. | Statut |
|---|---|---|---|---|
| F25 | [Prédictions batch et export Supabase agrégé](F25-batch-export-supabase.md) | F22 | M | todo |
| F26 | [API FastAPI](F26-api-fastapi.md) | F25 | M | todo |
| F27 | [Front Next.js](F27-web-nextjs.md) | F26 | L | todo |

## Phase 8 — Exploitation

| ID | Feature | Dépend de | Est. | Statut |
|---|---|---|---|---|
| F28 | [Orchestration complète et monitoring](F28-orchestration-monitoring.md) | F10, F25 | M | todo |
| F29 | [Model card, data card, AIPD et réentraînement](F29-docs-cards-retraining.md) | F22, F27 | M | todo |

## Graphe des dépendances

```
F00 ─┬─ F01 ── F03 ─┬─ F05 ─┐
     │              ├─ F06 ─┼─ F09 ─┬─ F10 ─┬─ F11
     └─ F02 ── F04 ─┤       │       │       ├─ F12 ─┐
                    ├─ F07 ─┘       │       ├─ F13 ─┼─ F16 ── F17 ── F18 ─┬─ F19 ── F20 ─┬─ F21 ── F22 ── F25 ── F26 ── F27
                    ├─ F08 ─────────┘       │       │                     │              └─ F23
                    └─ F14 ── F15 ──────────┘(F09)  │                     └─ F24
                                                                          F28 ← F10, F25 ; F29 ← F22, F27
```

## Jalons humains (hors Claude Code)

| Avant | Action humaine |
|---|---|
| F05 (run réel) | Réponse d'allrugby / validation juridique → `authorized: true` |
| F06 (run réel) | Réponse de la LNR → `authorized: true` |
| F14 (run réel) | Choix des flux presse autorisés |
| F15 | Clé API LLM dans `.env`, budget validé |
| F16 | Annotation manuelle de 300 à 500 épisodes (≈ 6–10 h) ; avis juriste sur art. 9 |
| F22 → F25 | Revue du rapport de modèle et promotion manuelle |
| F27 | Compte Vercel + projet Supabase |

Toutes les features peuvent être **développées et testées sur fixtures** sans autorisation ; seule l'exécution réelle de la collecte en dépend.
