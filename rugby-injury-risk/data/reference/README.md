# Références — état de validation

Mise à jour : 2026-11-03. Saisie : agent de développement ; validation métier et maintenance : porteur du projet (à confirmer).
`NULL` signifie inconnu, jamais zéro. Aucun fichier nominatif n'est prérempli.

| Fichier | Source | État |
|---|---|---|
| positions.csv | docs/04-data-model.md §1 | Vocabulaire contractuel exact |
| competitions.csv | docs/04-data-model.md §1 | Vocabulaire contractuel |
| venues.csv | Saisie manuelle des stades principaux | Coordonnées toutes NULL ; délocalisations non exhaustives |
| venue_surface.csv | F02-reference-data.md, résumé APPE | Cinq synthétiques 2025-2026 repris de la fiche, document primaire non retrouvé ; autres combinaisons absentes = unknown |
| test_windows.csv | Wikipédia, éditions Six Nations 2014–2027 et RWC 2015/2019/2023 | Partiel : fenêtres été/automne manquantes |
| rules_protection.csv | docs/01-data-sources.md §5 | Régimes repris du cadrage ; transitions 2014/2017/2018 fixées au 1er juillet par convention à confirmer |
| protected_players.csv | Humain | En-têtes seuls |
| opt_out.csv | Demandes d'opposition humaines | En-têtes seuls |
| er_overrides.csv | Revue humaine F09 | En-têtes seuls ; player_id entier ou NEW/REJECT |

## Calendrier

Bornes inclusives : premier au dernier match du tournoi, pas dates de mise à disposition des joueurs. Les reports 2020 sont séparés (février–mars / octobre), pour ne pas classer tout l'été en fenêtre internationale. Dates 2027 programmées, à revérifier après report éventuel.

Sources consultées le 2026-11-03 :
- `https://en.wikipedia.org/wiki/<YYYY>_Six_Nations_Championship` pour chaque année 2014 à 2027.
- https://en.wikipedia.org/wiki/2015_Rugby_World_Cup
- https://en.wikipedia.org/wiki/2019_Rugby_World_Cup
- https://en.wikipedia.org/wiki/2023_Rugby_World_Cup
- Calendrier officiel 2027 référencé : https://www.sixnationsrugby.com/en/m6n/news/mens-six-nations-2027-fixtures-and-schedule-confirmed

Données dérivées de Wikipédia : attribution aux contributeurs des pages citées, CC BY-SA ; revue de licence avant redistribution.

## Limites bloquantes avant usage analytique

- Compléter été/automne, notamment exceptions COVID et Nations Championship. `in_test_window=False` signifie absence dans ce référentiel **partiel**, pas preuve d'absence de sélection.
- Vérifier surfaces APPE sur document officiel ; ne pas utiliser ces cinq valeurs comme données auditées.
- Vérifier dates exactes d'entrée en vigueur des conventions ; aucun régime connu avant juillet 2014 ou après juin 2027 (`unknown`).
- Géolocaliser manuellement les 24 stades (IDs 1–24), ajouter délocalisations et nouveaux stades après audit.
- Les cinq terrains de la fiche incluent des clubs de Pro D2 : ils sont conservés pour traçabilité, pas assimilés à des participations Top 14.

Pas de scraping de matchs effectué. BDD non créée (F04). Registre des autorisations inchangé.
