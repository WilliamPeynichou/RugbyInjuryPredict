# Fixtures allrugby

Pages **réelles** capturées le 2026-11-06 après l'autorisation humaine de `allrugby`
(scripts, styles, SVG et en-tête de navigation retirés ; tableaux par saison retirés des
pages joueur pour la taille). Usage : tests de parseurs uniquement, pas de redistribution.

| Fichier | Cas couvert |
|---|---|
| `calendar_top14_2024.html` | calendrier Top 14 2023-2024 : 188 liens de match |
| `match_standard.html` | J22 Bayonne–Bordeaux, coup d'envoi 17h00, re-entrée (HUGUET 54' puis 74') |
| `match_reentry_no_venue.html` | J1 Bayonne–Toulouse, stade vide, HÉGUY 48' (= page joueur) |
| `match_final_yellow.html` | finale 2024, un carton jaune (`div.cj`) |
| `match_prod2_red.html` | Pro D2 (quarantaine) ; cartons rouges (`div.cr`) testés en la relabellisant Top 14 |
| `player_jiff.html` | profil JIFF, taille/poids, poste, JSON-LD `Person` |
| `player_non_jiff.html` | profil non JIFF, nationalité étrangère |
