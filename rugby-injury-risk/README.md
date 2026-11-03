# Rugby Injury Risk — risque de blessure par poste et enchaînement de matchs

Projet de data science qui estime la probabilité de blessure au prochain match pour chaque **poste** de rugby à XV professionnel (Top 14, internationaux, coupes d'Europe), en fonction du **nombre de matchs consécutifs**, de la **charge de matchs passée** et des **antécédents**.

> Ce dépôt est conçu pour être construit feature par feature par Claude Code. Le point d'entrée pour l'agent est `CLAUDE.md`. Le point d'entrée pour un humain est ce fichier.

## Ce que le projet produit

1. **Un entrepôt de données propre** des participations aux matchs (qui a joué, combien de minutes, à quel poste) depuis 2013/14, internationaux et coupes d'Europe inclus.
2. **Une base reconstruite d'épisodes de blessure** à partir de signaux publics croisés (sorties précoces, absences, annonces), avec un score de confiance par épisode.
3. **Des modèles de risque calibrés** : baseline par poste → hazard en temps discret → modèle hiérarchique bayésien par poste (modèle de production) → challenger gradient boosting.
4. **Un tableau de bord public agrégé** : courbes « risque vs matchs consécutifs » par poste, simulateur de scénarios, page méthodologie.

## Ce que le projet ne produit pas

- Un score de risque nominatif public (données de santé, RGPD art. 9).
- Une prédiction individuelle fiable : la littérature plafonne autour d'une AUC de 0,66 même avec GPS et données médicales internes. L'objectif réaliste est la **calibration au niveau poste**.
- Une conclusion causale : les associations charge → blessure sont confondues par la sélection des joueurs aptes.

## Organisation de la documentation

| Fichier | Contenu |
|---|---|
| `CLAUDE.md` | Règles de travail pour Claude Code |
| `docs/00-vision.md` | Problème, question précise, livrables, critères de succès |
| `docs/01-data-sources.md` | Sources classées, accès, risques, granularité |
| `docs/02-science-priors.md` | Littérature, chiffres de référence, priors |
| `docs/03-architecture.md` | Architecture technique bout en bout |
| `docs/04-data-model.md` | Schéma complet (dimensions, faits, table ML) |
| `docs/05-features-spec.md` | Définition exacte de chaque feature |
| `docs/06-modeling.md` | Formulation, modèles, validation, métriques |
| `docs/07-legal-rgpd.md` | Cadre juridique, garde-fous, AIPD |
| `docs/08-conventions.md` | Conventions de code, tests, git |
| `docs/09-glossary.md` | Glossaire rugby + data |
| `docs/10-implementation-status.md` | État d'implémentation : ce qui est fait, décisions, écarts, commandes |
| `features/ROADMAP.md` | Liste ordonnée des features, dépendances, statuts |
| `features/Fxx-*.md` | Une fiche par feature, exécutable par Claude Code |

## Démarrage rapide (après F00)

```bash
git clone <repo> && cd rugby-injury-risk
cp .env.example .env        # renseigner les clés
make setup                 # nécessite uv ; installe Python 3.12 et les hooks
make check
# make dagster sera disponible après F05
```

## Démarrer avec Claude Code

```bash
cd rugby-injury-risk
claude
> /feature F00
```

Puis enchaîner les features dans l'ordre de `features/ROADMAP.md`.

## Prérequis avant la première collecte réelle

- Demandes d'autorisation envoyées aux sources dont les CGU restreignent l'extraction (voir `docs/07-legal-rgpd.md`).
- `config/sources.yaml` mis à jour par un humain (`authorized: true` uniquement après accord ou validation juridique).
