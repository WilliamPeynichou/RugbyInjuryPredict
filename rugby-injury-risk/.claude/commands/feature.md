---
description: Implémente une feature de la roadmap (ex. /feature F05)
argument-hint: <Fxx>
---

Tu vas implémenter la feature **$ARGUMENTS** de ce dépôt.

1. Lis `CLAUDE.md` (règles d'or et workflow) si ce n'est pas déjà fait dans cette session.
2. Ouvre `features/ROADMAP.md` et vérifie que toutes les dépendances de $ARGUMENTS sont au statut `done`. Si ce n'est pas le cas, arrête-toi et indique lesquelles manquent.
3. Lis intégralement la fiche `features/$ARGUMENTS-*.md` et chaque document listé dans sa section « Docs de référence ».
4. Passe $ARGUMENTS à `in_progress` dans `ROADMAP.md` et crée la branche `feat/$ARGUMENTS-<slug>`.
5. Propose en 10 lignes maximum ton plan d'implémentation (fichiers, tests), puis exécute-le sans attendre sauf si un point est bloquant.
6. Écris les tests de la fiche avec le code. Aucun appel réseau dans les tests.
7. Lance `make check` jusqu'à ce que tout soit vert.
8. Coche les critères d'acceptation tenus dans la fiche ; consigne tout écart dans la section « Journal ».
9. Passe $ARGUMENTS à `done` dans `ROADMAP.md`, commit `feat($ARGUMENTS): <résumé>`.
10. Termine par un résumé de 5 lignes maximum : fait, écarts, prochaine feature débloquée.
