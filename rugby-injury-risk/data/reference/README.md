# Références — état de validation

Mise à jour : 2026-11-03. Saisie : agent de développement ; validation métier et maintenance : porteur du projet (à confirmer).
`NULL` signifie inconnu, jamais zéro. Aucun fichier nominatif n'est prérempli.

| Fichier | Source | État |
|---|---|---|
| positions.csv | docs/04-data-model.md §1 | Vocabulaire contractuel exact |
| competitions.csv | docs/04-data-model.md §1 | Vocabulaire contractuel |
| venues.csv | Saisie manuelle des stades principaux | Coordonnées toutes NULL ; délocalisations non exhaustives |
| venue_surface.csv | LNR, classement APPE publié le 02/07/2026 | Cinq synthétiques 2025-2026 confirmés par la page officielle ; autres combinaisons absentes = unknown |
| test_windows.csv | Wikipédia, éditions Six Nations 2014–2027 et RWC 2015/2019/2023 | Partiel : été 2014/15/17/18/21/22/24/25, automne 2013/14/17/18/20/24/25 ajoutés ; voir limites |
| rules_protection.csv | Source 42 du document de recherche ; docs/01-data-sources.md §5 pour 2026 | Plafond 2014-2015 borné ; annonces 2016/2017/2018 et groupes élargis dès 2020 ; voir conventions de dates ci-dessous |
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

- https://en.wikipedia.org/wiki/Autumn_Nations_Cup — 13/11–06/12/2020.
- https://en.wikipedia.org/wiki/2026_Nations_Championship — 04/07–18/07 et 06/11–29/11/2026, phase de novembre programmée.
- https://fr.wikipedia.org/wiki/Liste_%C3%89lite_des_joueurs_prot%C3%A9g%C3%A9s_par_la_convention_FFR/LNR — historique des protections.

- https://en.wikipedia.org/wiki/2024_mid-year_rugby_union_tests — période 22/06–27/07/2024, bornes vérifiées dans les sections du calendrier via API MediaWiki.
- https://en.wikipedia.org/wiki/2024_end-of-year_rugby_union_internationals — période 26/10–30/11/2024.
- https://en.wikipedia.org/wiki/2025_end-of-year_rugby_union_internationals — période 18/10–29/11/2025.

Ces périodes globales incluent les jours sans match entre les rencontres ; elles ne constituent pas des preuves de sélection ou de mise à disposition d'un joueur.

Données dérivées de Wikipédia : attribution aux contributeurs des pages citées, CC BY-SA ; revue de licence avant redistribution.

## Limites bloquantes avant usage analytique

- Vérification documentaire suspendue après réponse HTTP 429 de l'API Wikipédia ; aucune tentative de contournement. À reprendre à débit séquentiel espacé, après le délai du fournisseur. Fenêtres historiques été/automne encore manquantes, notamment 2013–2023 : ne pas substituer une fenêtre générique de juin/juillet ou novembre.
- Compléter été/automne, notamment exceptions COVID et Nations Championship. `in_test_window=False` signifie absence dans ce référentiel **partiel**, pas preuve d'absence de sélection.
- Surfaces APPE 2025-2026 confirmées : https://www.lnr.fr/actualite/le-classement-20252026-des-terrains-des-clubs-professionnels ; ne pas extrapoler aux autres saisons.
- Les régimes 2016/2017/2018 commencent aux dates d'annonce des listes (10/07/2016, 09/06/2017, 30/05/2018), pas à une date d'effet juridique vérifiée. Le changement décrit « à partir de 2020 » est représenté au 01/01/2020, précision annuelle seulement. `list_size=NULL` pour les groupes élargis : ne pas prolonger fictivement la liste de 40 jusqu'en 2026. Les intervalles se terminent la veille du changement suivant par convention de représentation. Les périodes sans source, notamment juin 2015–juillet 2016, renvoient `unknown`. Ces régimes restent à valider avant usage analytique.
- Géolocaliser manuellement les 24 stades (IDs 1–24), ajouter délocalisations et nouveaux stades après audit.
- Les cinq terrains de la fiche incluent des clubs de Pro D2 : ils sont conservés pour traçabilité, pas assimilés à des participations Top 14.

Pas de scraping de matchs effectué. BDD non créée (F04). Registre des autorisations inchangé.

## Fenêtres été/automne : limites
- Été 2020 : aucune fenêtre, tests annulés (COVID). Exception acceptée.
- Non sourcés, donc absents : été 2016, 2019 (partiel), 2023 ; automne 2015, 2016, 2021, 2022 (RWC couvre 2015 et 2023).
- Source : Wikipédia (API `tocdata`), bornes = premier/dernier match.
