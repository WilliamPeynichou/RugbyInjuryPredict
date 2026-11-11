# Risque de blessure par poste — tableau de bord

Front Next.js (App Router) qui affiche des chiffres agrégés par poste, Top 14, saisons 2022 à 2025.

- Lancer en local : `pnpm install`, puis `pnpm dev` (http://localhost:3000).
- Régénérer les données : `pnpm build:data` lit `../reports/public_preview/*.csv` et écrit `src/data/*.json`.
- Vérifier : `pnpm lint`, `pnpm typecheck`, `pnpm test`, `pnpm build`, `pnpm check:privacy`.
- Pages : `/` (tableau de bord) et `/methodologie` (sources, modèles, calibration, limites).
- Données : agrégées par poste et par saison, aucun joueur identifiable, aucun cookie, aucune API.
- Limites : blessures courtes sous-déclarées ; un seul découpage de validation ; biais de sélection.
- Association statistique, non causale. Ce site ne fait aucun pronostic sur un joueur.
- Le modèle principal n'est pas promu : la figure 2 est exploratoire et l'encadré le signale.
- Intervalles à 90 % : affichés sur chaque figure. Ne pas lire une barre sans son intervalle.
- Ne pas modifier les JSON à la main : relancer `pnpm build:data`.
- Stack : Next.js, TypeScript strict, CSS Modules, Recharts, Vitest + Testing Library.
