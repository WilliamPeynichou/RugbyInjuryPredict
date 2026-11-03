# 01 — Sources de données

Ce document classe les sources, décrit ce qu'elles fournissent et fixe les règles d'usage. Le statut d'autorisation effectif de chaque source vit dans `config/sources.yaml` (champ `authorized`), modifiable **uniquement par un humain**.

## 1. Tableau classé

| Rang | Source (`source_id`) | Données | Accès | Coût | Risque juridique | Fiabilité | Rôle dans le projet |
|---|---|---|---|---|---|---|---|
| 1 | **allrugby** (`allrugby`) | Feuilles de match Top 14 depuis sept. 2013 ; par joueur-match : n° de maillot (1–15 titulaire, 16–23 banc), minutes, cartons, points ; profils (taille, poids, JIFF, postes joués en %) ; Pro D2, coupes d'Europe, tests | Scraping HTML, pages joueurs `allrugby.com/joueurs/{slug}-{id}.html` | Gratuit (Premium 3 €/mois) | Moyen : droit sui generis probable, autorisation à demander | Élevée pour les minutes | **Source primaire des minutes** |
| 2 | **LNR officiel** (`lnr`) | Feuilles de match : XV de départ + remplaçants, poste, nationalité, ID joueur stable ; classement « temps de jeu » | Scraping HTML `top14.lnr.fr/feuille-de-match/{saison}/j{journée}/{id}-{dom}-{ext}/compositions` ; pas d'API publique | Gratuit | **Élevé** : CGU (16/06/2023) interdisent reproduction hors usage privé et accès autrement que par l'interface | Référence officielle | **Référentiel d'identifiants**, réconciliation ponctuelle |
| 3 | **itsrugby** (`itsrugby`) | Historique match par match avec minutes ; notes libres de blessure (date, zone, durée parfois « non communiquée ») ; enquêtes infirmerie | Scraping HTML | Gratuit | **Élevé** : CGU interdisent l'extraction substantielle, droit sui generis revendiqué | Bonne (minutes), partielle (blessures) | Vérité terrain partielle des blessures, **uniquement si autorisé** |
| 4 | **ESPN** (`espn`) | Compositions Top 14 (league id 270559), scores, stats ; `site.api.espn.com/apis/site/v2/sports/rugby/{leagueId}/summary?event={gameId}` | JSON non documenté | Gratuit | Moyen | Couverture lineups historique incomplète | Internationaux, coupes d'Europe, calendrier |
| 5 | **Sportradar Rugby v3** (`sportradar`) | Lineups saison et match, timeline avec `substituted_in/out`, stats joueur depuis déc. 2022 | API contractuelle | Sur devis | Faible | Élevée ; `starter` ne distingue pas titulaire et « a joué » | Option payante si produit |
| 6 | **Stats Perform / Opta** | Événementiel fin | Contrat | Élevé | Faible | Référence industrielle | Hors MVP |
| 7 | **World Rugby** (`worldrugby`) | Matchs internationaux, minutes par joueur | JSON non documenté (API pulselive) | Gratuit | Moyen | Bonne pour les tests | **Source primaire des internationaux** |
| 8 | **Dépôts GitHub** | `hans-brgs/rugby-data-scraper` (ETL ESPN), `transientlunatic/Rugby-Data` (scores Top 14 2009-10 → 2021-22), `bpcsaund/rugby-analytics` (lineups multi-ligues + SQLite, appariement flou) | Clonage | Gratuit | Hérite des sources amont | Variable | Amorçage, inspiration, tests croisés |
| 9 | **API-Sports rugby** (`apisports`) | Calendrier, résultats, classements (144 ligues) | REST | Freemium | Faible | Bonne | Calendrier de secours |
| 10 | DataSportsGroup, Highlightly, SportsAPI Pro | Lineups, profils | Commercial | Payant | Faible | À évaluer | Hors MVP |
| 11 | **Wikipédia** (`wikipedia`) | Stades, capacités, historique convention FFR/LNR | API MediaWiki | Gratuit | Faible (CC BY-SA) | Contexte | Données de référence |
| 12 | **Presse et points médicaux** (`news`) | Annonces de blessures, type, durée estimée | RSS / HTML, extraction NLP | Gratuit / abonnement | Moyen à élevé | Bruitée, biaisée vers les joueurs médiatisés | Signal « annonce » |

Aucun jeu de données de blessures Top 14 n'a été identifié sur data.gouv.fr ou Kaggle.

## 2. Règles d'usage (implémentées dans F01 et F03)

1. Chaque source a une entrée dans `config/sources.yaml` avec : `authorized`, `base_url`, `min_delay_seconds`, `respect_robots`, `user_agent_contact`, `notes_legal`.
2. `authorized: false` par défaut pour `lnr`, `itsrugby`, `allrugby`, `news`. Le client HTTP **lève une exception** avant tout appel réseau.
3. Débit par défaut : une requête toutes les 3 secondes par domaine, maximum.
4. Cache HTTP (ETag, If-Modified-Since) et lac brut : jamais deux fois la même page si elle n'a pas changé.
5. Le développement se fait sur **fixtures figées** (`tests/fixtures/<source>/`), jamais sur le site.

## 3. Granularité réellement disponible

| Information | Disponible ? | Comment |
|---|---|---|
| Minutes jouées par match | Oui | allrugby, itsrugby, stats LNR |
| Minute d'entrée / de sortie | Déduite | Titulaire avec 52' : sorti à la 52e. Remplaçant avec 28' : entré vers la 52e. Native dans la timeline Sportradar |
| Motif de sortie (tactique / blessure / HIA) | **Non structuré** | Comptes rendus, presse, annotation (F12, F15) |
| Charge d'entraînement, GPS | Non public | Hors périmètre : le modèle porte sur la charge de **match** |
| Poste joué | Oui | n° de maillot + LNR + allrugby (% par poste) |
| Profil (naissance, taille, poids) | Oui | allrugby, LNR |

## 4. Données de blessure : stratégie de reconstruction

Aucune source publique ne fournit d'historique structuré. L'enquête médicale mensuelle obligatoire de la LNR (renseignée par les médecins de club depuis 2006/2007) n'est pas publique ; c'est la cible d'un partenariat ultérieur.

On croise trois signaux (détails dans F12–F16) :

1. **Sortie** : titulaire sorti avant la 60e, ou remplaçant ressorti après être entré.
2. **Annonce** : extraction LLM d'articles et de points médicaux.
3. **Absence** : séquence sans feuille de match alors que le club joue, classée en blessure, sélection, suspension, repos protégé ou rotation.

Définition d'un épisode et biais : voir `04-data-model.md` (`fact_injury_event`) et `02-science-priors.md`.

## 5. Données contextuelles

| Donnée | Source | Fichier de référence |
|---|---|---|
| Calendrier, coups d'envoi | LNR, ESPN, API-Sports | `fact_match` |
| Surface par stade et saison | Classement APPE annuel des terrains (LNR) | `data/reference/venue_surface.csv` |
| Coordonnées des stades | Wikipédia / géocodage manuel | `data/reference/venues.csv` |
| Calendrier des tests | World Rugby, Wikipédia | `data/reference/test_windows.csv` |
| Listes de joueurs protégés (convention FFR/LNR) | FFR, presse, Wikipédia | `data/reference/protected_players.csv` (+ `rules_protection.csv`) |
| Profils joueurs | allrugby, LNR | `dim_player` |

Historique de la convention FFR/LNR à encoder dans `rules_protection.csv` :
- 2014-15 : Liste Élite de 30 joueurs plafonnés à 30 matchs (un match compte à partir de 20 minutes).
- 2017 : liste portée à 45 joueurs.
- 2018 : 40 joueurs, dix semaines d'intersaison sans match.
- Depuis le 1er juillet 2026 : 33 internationaux protégés (liste non publiée intégralement), un week-end de repos sur quatre (ou deux sur huit), au plus neuf sélections sur les douze tests de la saison.

## 6. Contacts d'autorisation (phase 0)

- LNR : contact@lnr.fr — demande d'usage de recherche non commercial des feuilles de match.
- allrugby : formulaire de contact du site.
- itsrugby : contact éditeur (RUCK ZONE).

Modèle de courriel : `docs/07-legal-rgpd.md`, section 6.
