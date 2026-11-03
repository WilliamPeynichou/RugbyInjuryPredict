# F27 — Front Next.js

| Champ | Valeur |
|---|---|
| Phase | 7 |
| Dépendances | F26 |
| Estimation | L |
| Docs de référence | `docs/03-architecture.md` §2.8, `docs/08-conventions.md` §7, `docs/00-vision.md` |

## Objectif

Un site public, sobre et pédagogique, qui montre le risque de blessure par poste en fonction des matchs consécutifs, permet de simuler des scénarios et explique la méthode et ses limites.

## Contexte

Livrable visible du projet (portfolio, échanges avec la LNR / des staffs). Le message clé : des **ordres de grandeur calibrés par poste**, avec incertitude, pas des prédictions individuelles.

## Périmètre

- [ ] `web/` : Next.js App Router, TypeScript strict, pnpm, ESLint + Prettier, Tailwind (ou CSS modules), bibliothèque de graphiques (Recharts ou Visx — choix justifié).
- [ ] Client typé généré depuis `web/openapi.json` (`openapi-typescript` + fetch typé).
- [ ] Pages :
  - `/` — question, réponse en une phrase, graphique principal (h(N) des 9 postes, scénario médian), chiffres clés, avertissement ;
  - `/postes/[code]` — courbe du poste avec intervalle à 90 %, comparaison avec son groupe, incidence par saison, gravité médiane ;
  - `/simulateur` — choix du poste, du scénario et de K ; risque au prochain match et cumulé sur K matchs ; lecture en langage simple (« sur 100 joueurs dans cette situation, environ X se blessent au prochain match ») ;
  - `/comparer` — superposition de 2 à 4 postes ;
  - `/methodologie` — données, labellisation, modèle, calibration (graphique), limites (sous-déclaration, biais de sélection, non-causalité), sources ;
  - `/a-propos` — projet, contact, mentions RGPD.
- [ ] Chaque graphique a un tableau alternatif accessible et une mention « association, non causale ».
- [ ] Composants serveur par défaut ; simulateur en composant client.
- [ ] Mode sombre, responsive mobile.
- [ ] Déploiement Vercel : `web/vercel.json` si nécessaire, variable `NEXT_PUBLIC_API_URL`.

## Hors périmètre

- Comptes utilisateurs, données nominatives, classements de clubs.

## Fichiers

| Fichier | Action |
|---|---|
| `web/**` | créer |

## Tests

- Tests unitaires (Vitest) des fonctions de formatage (probabilités → « X sur 100 », intervalles).
- Tests de composants (Testing Library) : simulateur met à jour le résultat.
- Test e2e minimal (Playwright) : la page d'accueil charge et affiche 9 courbes (API mockée).
- `pnpm lint && pnpm typecheck && pnpm test` intégré à `make check-web` et à la CI.

## Critères d'acceptation

- [ ] `make web` lance le site sur l'API locale.
- [ ] Lighthouse accessibilité ≥ 90 sur `/` et `/simulateur`.
- [ ] Aucune donnée nominative affichée ni présente dans le bundle (test grep sur `.next/`).
- [ ] CI web verte.

## Journal

