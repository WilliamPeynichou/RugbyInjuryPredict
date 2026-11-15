# F14 — Collecte presse et points médicaux

| Champ | Valeur |
|---|---|
| Phase | 3 |
| Dépendances | F03, F04 |
| Estimation | M |
| Docs de référence | `docs/01-data-sources.md` §1 (news), `docs/07-legal-rgpd.md` §3 |

## Objectif

Collecter, à partir de flux explicitement autorisés, les articles et communiqués susceptibles de mentionner des blessures (points médicaux de clubs, brèves infirmerie), et les stocker sous forme de documents texte normalisés.

## Contexte

Source du signal « annonce ». Les flux sont choisis par l'humain dans `config/sources.yaml` (`news.feeds`). On ne conserve que le texte utile et des métadonnées ; les livrables ne contiennent jamais d'article complet.

## Périmètre

- [ ] Ajouter `feedparser` (justifier dans le journal) et `trafilatura` ou équivalent léger pour extraire le texte principal d'une page HTML.
- [ ] `sources/news/feeds.py` : lecture des flux RSS/Atom configurés via `PoliteClient` (source `news`).
- [ ] `sources/news/articles.py` : récupération de la page d'article (même client), extraction du texte, titre, date de publication, club(s) mentionné(s).
- [ ] Pré-filtre lexical (`config/news_keywords.yaml`) : blessure, blessé, infirmerie, forfait, indisponible, commotion, protocole, opéré, rupture, entorse, élongation, fracture, déchirure, semaines d'arrêt, etc. Seuls les articles passant le filtre sont gardés en staging.
- [ ] Staging `news_documents` : `doc_id (sha256 URL canonique), source_feed, url, published_at, title, text, clubs_detected, keyword_hits, fetched_at`.
- [ ] Rétention : `text` conservé dans le staging local uniquement (gitignored), jamais exporté.
- [ ] Asset Dagster `news_documents` partitionné par semaine.
- [ ] Fixtures : 5 articles (point médical de club, brève multi-joueurs, article sans blessure, article avec durée annoncée, article sur une commotion).

## Hors périmètre

- Extraction structurée des blessures (F15). Contournement de paywalls (interdit).

## Spécification technique

Détection des clubs : dictionnaire depuis `team_aliases.csv` (F08), correspondance de mots entiers insensible aux accents.

## Fichiers

| Fichier | Action |
|---|---|
| `src/rugby_risk/sources/news/{__init__,feeds,articles,filters}.py` | créer |
| `config/news_keywords.yaml` | créer |
| `orchestration/assets/news.py` | créer |
| `tests/fixtures/news/*` | créer |

## Tests

- `tests/unit/news/test_filters.py` — l'article sans blessure est écarté, les 4 autres retenus ; clubs détectés.
- `tests/unit/news/test_articles.py` — extraction du texte et de la date sur fixtures HTML.
- `tests/integration/news/test_news_asset.py` — idempotence (même URL → même `doc_id`, pas de doublon).

## Critères d'acceptation

- [ ] Avec `news.feeds: []`, l'asset s'exécute sans rien collecter et sans erreur.
- [ ] Les 5 fixtures donnent le résultat attendu.
- [ ] `make check` vert.

## Journal

- **Statut corrigé le 2026-11-10** : fiche repassée en `todo`. Jamais réalisée feature par feature ; les cases ci-dessus sont vides et le code de collecte presse est hérité de F03 sans relecture. `news` reste désactivé (`authorized: false`) sans décision humaine.

