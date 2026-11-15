# F30 — Simulateur de profil de charge par poste

| Champ | Valeur |
|---|---|
| Phase | 5 |
| Dépendances | F22 |
| Estimation | M |
| Docs de référence | `docs/06-modeling.md` §1-2 et §6, `docs/07-legal-rgpd.md` §2 et §4, `docs/02-science-priors.md` §5 |

## Objectif

Répondre à la question « pour un joueur de ce poste, avec cette charge, quel risque de
blessure à chaque match enchaîné ? » à partir du modèle M2, avec intervalles crédibles à 90 %
et un avertissement explicite. L'étude reste **par poste** : le joueur n'est qu'un profil de
charge saisi, jamais un nom ni un identifiant.

## Contexte

Demande humaine du 2026-11-08 : associer un profil de joueur (poste, titulaire ou remplaçant,
matchs club et internationaux, matchs enchaînés) à l'étude par poste. Les courbes F22 figent
tout au profil médian ; ici l'utilisateur fixe les variables de charge. Nécessite un
ajustement final (toutes les saisons validées) persisté, car le M2 n'était ajusté que par fold.

## Périmètre

- [x] `runner.fit_final` : ajustement sur toutes les saisons hors test final gelé, mêmes
      filtres que les folds (lignes jouées, label observable, éligibles pour l'IPW). Le runner
      reste le seul point d'entrée d'entraînement.
- [x] `modeling/artifact.py` : persistance locale d'un M2 ajusté (`data/models/<run_id>/`) :
      tirages postérieurs (sans effets joueur/équipe), index des postes, profils, transform.
      patsy n'étant pas sérialisable, le design est reconstruit depuis les colonnes de
      features du train (sans `player_key`, sans cible) et vérifié à l'identique.
- [x] `modeling/profile.py` : `PositionProfile` (poste, minutes par match, matchs ≥ 20 min sur
      365 j club + sélection, minutes sur 28 j, fenêtre internationale, N de départ, horizon),
      risque par match avec IC90, risque cumulé par tirage, facteur multiplicatif par match
      enchaîné, avertissement.
- [x] CLI `rugby-risk fit-final <modèle>` et `rugby-risk profile ...`.

## Hors périmètre

- Toute sortie nominative (aucun argument de nom, aucun `player_key`).
- Export public (F25), API (F26), front (F27).
- Promotion du modèle : reste une décision humaine (jalon F22 → F25).

## Spécification technique

- Joueur et équipe-saison du profil = inconnus : effets intégrés (Gauss-Hermite, F22).
- `consecutive_matches` = matchs consécutifs joués (titulaire ou non) ; il est plafonné au
  P99 du train (winsorisation du design) : tout N au-delà est signalé comme extrapolé.
- Charge sur 28 j figée sur l'horizon (ceteris paribus, comme `configs/scenarios.yaml`).
- `profile` refuse un artefact dont le MCMC est en échec (docs/06 §6) et affiche « modèle non
  promu » tant qu'aucune promotion humaine n'est enregistrée.

## Fichiers

| Fichier | Action |
|---|---|
| `src/rugby_risk/modeling/runner.py` | modifier (`fit_final`) |
| `src/rugby_risk/modeling/artifact.py` | créer |
| `src/rugby_risk/modeling/profile.py` | créer |
| `src/rugby_risk/cli.py` | modifier |

## Tests

- `tests/unit/modeling/test_profile.py` — IC90 ordonnés, cumul monotone, facteur > 1 si pente
  positive, N extrapolé signalé, refus MCMC en échec, aucune colonne nominative.
- `tests/unit/modeling/test_artifact.py` — aller-retour save/load : prédictions identiques,
  aucun `player_key` ni cible persistés, transform altéré détecté.
- `tests/unit/modeling/test_fit_final.py` — saison de test finale jamais utilisée.

## Critères d'acceptation

- [x] Aucune entrée ni sortie nominative (test).
- [x] Prédictions identiques avant/après persistance (test).
- [x] Avertissement et IC90 présents dans chaque sortie (test).
- [x] `make check` vert.

## Journal

- **Décision humaine (2026-11-08)** : l'étude reste par poste ; le joueur cité en exemple
  (Hugo Reus) ne sert qu'à illustrer un profil de charge. Aucun nom en entrée ni en sortie,
  intervalles crédibles et avertissement explicite obligatoires.
- **Persistance** : `patsy.DesignInfo` lève `NotImplementedError` au pickle (nœuds des
  splines). L'artefact stocke donc les colonnes de features du train (sans `player_key`, ids,
  ni cible) et reconstruit le transform au chargement ; les statistiques (médianes, bornes,
  moyennes, écarts-types, niveaux, formule) sont comparées à celles de l'ajustement, toute
  différence lève `ArtifactError`. Les effets joueur/équipe ne sont pas stockés : un profil
  est toujours un nouveau joueur et une nouvelle équipe-saison (intégrés, F22).
- **`fit_final`** est dans le runner (seul point d'entrée d'entraînement) ; il exclut
  `FINAL_TEST_SEASON` et n'est jamais évalué sur ses propres lignes : la qualité prédictive
  reste celle de la revue en rolling origin (F22).
- **Lecture du facteur par match** : moyenne géométrique, par tirage, de h(N+1)/h(N) sur
  l'horizon ; un IC90 contenant 1 = pas d'effet établi. Le modèle est cloglog linéaire en N
  (standardisé) : il peut représenter une hausse multiplicative, il ne l'impose pas.
- **Limites** : `consecutive_matches` compte les matchs joués (titulaire ou non), pas les
  titularisations ; charge 28 j figée ; N plafonné au P99 du train (signalé).
- **Run réel (2026-11-08)** : `rugby-risk fit-final` sur 2022-2025 (23 382 lignes, dataset v7
  `7d004d9a`), MCMC ok (R̂ 1,0089, ESS 623/783, 0 divergence, 19 min). Artefact
  `m2_hierarchical-20261108T234650Z`, non promu. Profil FLY_HALF titulaire (80 min, 22 matchs
  sur 365 j, 320 min sur 28 j) : 2,0 % [1,2 ; 3,0] au premier match, cumul 12,9 %
  [8,6 ; 18,2] sur 8 matchs ; facteur par match enchaîné 0,964 [0,895 ; 1,013] : **aucune
  hausse établie** avec 3 saisons (cohérent avec l'effet « survivant en bonne santé »,
  docs/02 §3). Le `git_sha` de l'artefact est celui d'avant le commit F30 (code non commité au
  moment du run).

