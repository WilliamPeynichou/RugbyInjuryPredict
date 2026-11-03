# 07 — Cadre juridique, RGPD et éthique

> Document de référence. Claude Code ne le modifie pas sans demande explicite de l'humain. Ce document n'est pas un avis juridique : il liste les points à valider avec un juriste.

## 1. Qualification des données

| Donnée | Qualification | Conséquence |
|---|---|---|
| Participation aux matchs (minutes, poste) | Donnée personnelle (personne identifiable), non sensible | RGPD applicable : finalité, minimisation, information |
| Blessure rattachée à un joueur identifié | **Donnée concernant la santé (art. 9 RGPD)** | Interdiction de principe, exceptions strictes |
| Profil (âge, taille, poids, nationalité) | Donnée personnelle | Minimisation |
| Agrégats par poste avec ≥ 10 joueurs distincts | Donnée anonymisée (sous réserve de non-réidentification) | Publiable |

L'exception « données manifestement rendues publiques » (art. 9.2.e) vise ce que **la personne concernée** a elle-même rendu public. Une annonce de club ou un article de presse ne suffit pas. L'exception journalistique ne couvre pas un projet de ML.

Base envisagée : recherche scientifique (art. 9.2.j et art. 89) avec garanties appropriées. **À valider avec un juriste avant la phase 3 (blessures).**

## 2. Garde-fous techniques (implémentés et testés)

| Garde-fou | Où | Feature |
|---|---|---|
| Pseudonymisation : `player_key = HMAC-SHA256(player_id, PSEUDONYM_SALT)[:16]`, sel hors dépôt | `ml_player_match`, MLflow, rapports | F04, F17 |
| Aucun nom, aucun `player_id` dans les tables ML, artefacts MLflow et logs | Tests automatiques sur colonnes et logs | F17, F18 |
| Données nominatives de blessure confinées à `data/` et `warehouse.duckdb` (gitignored, chiffrement disque recommandé) | `.gitignore`, test pre-commit | F00, F16 |
| Export public : agrégats uniquement, suppression des cellules < 10 joueurs distincts | `serving/guard.py` | F25 |
| API sans endpoint nominatif ; test qui échoue si une réponse contient une colonne listée dans `FORBIDDEN_PUBLIC_COLUMNS` | `api/` | F26 |
| Durée de conservation : données nominatives de blessure supprimées 5 ans après la fin du projet de recherche, ou sur demande | `docs/` + commande `make purge-health` | F29 |
| Droit d'opposition : `data/reference/opt_out.csv` (player_id exclus de tout traitement blessure) | dbt filtre amont | F16 |

## 3. Droit des bases de données et CGU

- **Droit sui generis** du producteur de base (art. L.341-1 CPI) : l'extraction substantielle d'une base protégée est interdite sans accord. Revendiqué par RUCK ZONE (itsrugby) et implicitement par la LNR.
- **CGU LNR** (16/06/2023) : licence limitée à la consultation, reproduction uniquement pour usage personnel et privé, interdiction d'accéder aux sites autrement que par l'interface.
- **Exception de fouille de textes et de données** (art. L.122-5-3 CPI, directive 2019/790 art. 4) : possible sous réserve d'absence d'opt-out explicite par le titulaire. **À valider avec un juriste.**
- **Presse** : droit d'auteur sur les articles. On ne stocke que des extraits courts (≤ 200 caractères) comme preuve, avec URL ; jamais l'article complet dans un livrable.

Règle opérationnelle : `authorized: true` dans `config/sources.yaml` uniquement après accord écrit ou validation juridique, avec la référence de l'accord dans `notes_legal`.

## 4. Éthique

- Un score de risque individuel public pourrait peser sur la valeur contractuelle ou la sélection d'un joueur → **jamais de sortie nominative**.
- Communication systématique de l'incertitude (intervalles) et des limites (sous-déclaration, biais de sélection).
- Pas de classement de clubs « les plus dangereux » : les différences entre clubs reflètent autant les politiques de communication médicale que le risque réel.

## 5. AIPD (analyse d'impact) — trame à compléter en F29

1. Description du traitement, finalités, base légale.
2. Nécessité et proportionnalité (minimisation, durée de conservation).
3. Risques pour les personnes (réidentification, fuite, usage contractuel).
4. Mesures (pseudonymisation, agrégation, k ≥ 10, confinement, opt-out).
5. Avis du DPO / juriste.

## 6. Modèle de demande d'autorisation (phase 0)

> Objet : Demande d'autorisation d'usage de données de feuilles de match à des fins de recherche
>
> Bonjour,
>
> Je mène un projet de recherche non commercial en data science sur le lien entre l'enchaînement des matchs et le risque de blessure par poste dans le rugby professionnel français. Je souhaiterais utiliser les compositions et temps de jeu publiés sur votre site pour les saisons 2013-2014 à aujourd'hui.
>
> Modalités proposées : collecte à faible débit (une page toutes les 3 secondes maximum), identification claire du client, aucune redistribution des données brutes, publication uniquement de résultats agrégés par poste.
>
> Je reste à votre disposition pour présenter la méthodologie ou envisager un partenariat.
>
> Cordialement,
> [Nom, coordonnées]

## 7. Points à valider avec un juriste (checklist)

- [ ] Base légale du traitement des données de santé reconstruites (art. 9.2.j + art. 89).
- [ ] Applicabilité de l'exception TDM aux sites visés (présence d'opt-out ?).
- [ ] Niveau d'agrégation suffisant pour l'anonymisation (k = 10 suffisant ?).
- [ ] Information des personnes concernées (art. 14 : exception pour effort disproportionné en recherche ?).
- [ ] Contrats avec les sources ayant donné leur accord.
