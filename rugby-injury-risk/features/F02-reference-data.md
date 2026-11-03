# F02 — Données de référence

| Champ | Valeur |
|---|---|
| Phase | 0 |
| Dépendances | F00 |
| Estimation | M |
| Docs de référence | `docs/04-data-model.md` §1, `docs/01-data-sources.md` §5 |

## Objectif

Versionner les vocabulaires contrôlés et les tables de contexte (postes, compétitions, stades, surfaces, fenêtres internationales, règles de protection) sous forme de CSV validés, avec un module d'accès unique.

## Contexte

Aucun poste, aucune compétition ne doit être écrit en dur dans le code (`CLAUDE.md` §7). Ces tables alimentent les dimensions dbt (F04) et plusieurs features (F17).

## Périmètre

- [x] `data/reference/positions.csv` (contenu exact de `docs/04-data-model.md` §1).
- [x] `data/reference/competitions.csv`.
- [ ] `data/reference/venues.csv` : les stades des clubs ayant joué en Top 14 depuis 2013-14 (nom, ville, lat, lon). Remplir ce qui est connu avec certitude ; les inconnus restent à `NULL` et sont listés dans le journal.
- [ ] `data/reference/venue_surface.csv` : colonnes `venue_id, season_id, surface, source`. Pré-remplir 2025-2026 depuis le classement APPE LNR (Montauban, Biarritz, Provence Rugby, Mont-de-Marsan, Racing 92 en synthétique) ; autres saisons `unknown` à compléter par l'humain.
- [ ] `data/reference/test_windows.csv` : `window_id, label, start_date, end_date, type` (six_nations, autumn, summer, rwc) de 2013-14 à 2026-27.
- [ ] `data/reference/rules_protection.csv` : régimes de la convention FFR/LNR (`docs/01-data-sources.md` §5).
- [x] `data/reference/protected_players.csv` : en-têtes seulement (`season_id, player_name, source_url`), rempli par l'humain.
- [x] `data/reference/opt_out.csv`, `er_overrides.csv` : en-têtes seulement.
- [x] `src/rugby_risk/reference.py` : chargeurs typés (`positions()`, `competitions()`, `test_windows()`…) avec validation Pandera et cache.
- [x] `data/reference/README.md` : source, date de mise à jour et responsable de chaque fichier.

## Hors périmètre

- Géocodage automatique des stades (manuel ou ultérieur). Remplissage des listes protégées (humain).

## Spécification technique

```python
def positions() -> pl.DataFrame: ...  # validé : 9 lignes, codes uniques
def position_group(code: str) -> str: ...
def position_from_shirt(n: int) -> str | None: ...  # 1..15 strict, None pour 16..23
def test_windows() -> pl.DataFrame: ...
def in_test_window(d: date) -> bool: ...
def protection_regime(d: date) -> str: ...
```

Schémas Pandera : dates cohérentes (`start_date ≤ end_date`), pas de chevauchement de fenêtres du même type, `surface ∈ {natural, hybrid, synthetic, unknown}`.

## Fichiers

| Fichier | Action |
|---|---|
| `data/reference/*.csv`, `data/reference/README.md` | créer |
| `src/rugby_risk/reference.py` | créer |

## Tests

- `tests/unit/test_reference.py` — chaque CSV passe son schéma ; `position_from_shirt(2) == "HOOKER"` ; `position_from_shirt(18) is None` ; `in_test_window` sur une date du Six Nations ; régime de protection correct au 1er juillet 2026.

## Critères d'acceptation

- [x] 9 postes, 6 groupes, 2 unités.
- [ ] `test_windows.csv` couvre toutes les saisons de `config/seasons.yaml`.
- [x] Aucune chaîne de poste en dur ailleurs que dans `positions.csv` (vérifié par un test grep sur `src/`).
- [x] `make check` vert.

## Journal

- Travail en cours sur `feat/F02-reference-data`. Registre des sources inchangé ; scraping de matchs différé jusqu'à validation de F04, conformément à la demande humaine.
- Recherche documentaire ponctuelle autorisée par l'humain. Six Nations 2014–2027 et Coupes du monde 2015/2019/2023 consultés sur Wikipédia ; liens et limites dans `data/reference/README.md`.
- Calendriers été/automne incomplets : F02 ne peut pas être déclarée terminée. Document APPE primaire non retrouvé ; cinq synthétiques repris uniquement de la fiche avec provenance explicite à confirmer.
- 24 stades préremplis, toutes coordonnées NULL ; délocalisations non exhaustives. Dates de transition 2014/2017/2018 des conventions représentées au 1er juillet par convention, à confirmer avant usage analytique.
- Validation locale : `make check` vert, 70 tests et couverture globale 98,97 %. CI distante non exécutée.
- Reprise après consultation du document de recherche : lien APPE exact retrouvé, cinq surfaces confirmées sur la page officielle publiée le 02/07/2026 ; provenance CSV remplacée par son URL.
- Autumn Nations Cup 2020 et deux phases du Nations Championship 2026 ajoutées après vérification documentaire. Le reste des fenêtres été/automne demeure incomplet : F02 reste `in_progress`.
- Correction des extrapolations du régime de protection : plafond 2014 borné à juin 2014–mai 2015, dispositifs 2016 et groupes élargis dès 2020 distingués. Les dates d'annonce et la précision annuelle sont documentées, sans les présenter comme dates d'effet juridique.
- Instruction de consultation prioritaire du document de recherche ajoutée à CLAUDE.md. Aucun changement des autorisations de collecte.
- Chargeurs Polars avec validation Pandera, cache et clones ; tests hors réseau. Les dates ISO nécessitent un parsing explicite avant validation Pandera.

