# Fixtures allrugby

Construites à la main (script `build_fixtures.py`, markup figé), car `allrugby` n'est pas
autorisée : aucune page réelle n'a été capturée. Le format reprend les éléments publics
documentés dans `docs/01-data-sources.md` (URL `joueurs/{slug}-{id}.html`, feuilles de match
avec n° de maillot 1–15 titulaire / 16–23 banc, minutes, cartons). **Hypothèses non vérifiées
sur le site réel :** slugs d'URL saison/match, balises exactes (`div.matchinfo`, `table.club_stats`,
`ul.fiche`), codage des cartons. À valider dès le premier crawl autorisé ; signaler les écarts
dans le journal de F05.

| Fichier | Cas couvert |
|---|---|
| `match_red_card.html` | match standard, heure de coup d'envoi présente, carton rouge (n°2, 51'), banc |
| `match_standard.html` | heure de coup d'envoi absente → imputée 15:00 locale + flag, remplaçants non entrés à 0' |
| `match_playoff.html` | phase finale (`top14-playoffs`, ronde « Demi ») |
| `player_full.html` | profil complet (naissance, taille, poids, nationalité, JIFF, sélections) |
| `player_partial.html` | profil incomplet sans exception |
