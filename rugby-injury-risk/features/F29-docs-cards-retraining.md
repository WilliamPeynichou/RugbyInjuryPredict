# F29 — Model card, data card, AIPD et réentraînement

| Champ | Valeur |
|---|---|
| Phase | 8 |
| Dépendances | F22, F27 |
| Estimation | M |
| Docs de référence | `docs/07-legal-rgpd.md` §2, §5, `docs/06-modeling.md` §5–6, `docs/00-vision.md` |

## Objectif

Documenter le système pour un lecteur externe (staff, LNR, recruteur, juriste) et outiller le cycle annuel de réentraînement et la purge des données de santé.

## Contexte

Un projet manipulant des données de santé reconstruites et publiant des probabilités doit être transparent sur ses données, ses limites et ses garde-fous.

## Périmètre

- [ ] `docs/model-card.md` (format Mitchell et al.) : usage prévu et non prévu, données, métriques par fold et par groupe de postes, calibration, limites, considérations éthiques — généré en partie automatiquement depuis le registre MLflow (`uv run rugby-risk docs model-card`).
- [ ] `docs/data-card.md` : sources, couverture par saison et compétition, procédure de labellisation, précision mesurée (F16), biais connus, licences et autorisations.
- [ ] `docs/aipd.md` : trame de `docs/07-legal-rgpd.md` §5 remplie avec l'état réel du projet ; points ouverts pour le juriste.
- [ ] `docs/runbook-retraining.md` : procédure de fin de saison (mise à jour `seasons.yaml`, surfaces, fenêtres, listes protégées ; `train_season` ; revue ; promotion ; `publish`) avec checklist.
- [ ] Commande `make purge-health` : supprime les tables et fichiers nominatifs de blessure (`fact_injury_event`, `injury_mentions`, annotations, cache LLM) après confirmation interactive, et journalise l'opération (sans contenu).
- [ ] Mise à jour de `README.md` : état du projet, liens vers le site, les cards et les rapports.
- [ ] Page `/methodologie` du front alimentée par le contenu de la model card (lien ou import Markdown).

## Hors périmètre

- Validation juridique elle-même (humaine).

## Fichiers

| Fichier | Action |
|---|---|
| `docs/{model-card,data-card,aipd,runbook-retraining}.md` | créer |
| `src/rugby_risk/docs_gen.py` | créer |
| `Makefile` | modifier (`purge-health`, `docs`) |
| `README.md` | modifier |

## Tests

- `tests/unit/test_docs_gen.py` — la model card générée contient toutes les sections et les métriques du run de référence (MLflow temporaire).
- `tests/unit/test_purge.py` — sur un entrepôt temporaire, la purge supprime exactement les objets listés et rien d'autre ; refuse sans confirmation.

## Critères d'acceptation

- [ ] Les quatre documents existent et sont cohérents avec le modèle promu.
- [ ] `make purge-health` testé sur entrepôt temporaire.
- [ ] `make check` vert.

## Journal

