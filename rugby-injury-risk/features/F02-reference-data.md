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

- [ ] `data/reference/positions.csv` (contenu exact de `docs/04-data-model.md` §1).
- [ ] `data/reference/competitions.csv`.
- [ ] `data/reference/venues.csv` : les stades des clubs ayant joué en Top 14 depuis 2013-14 (nom, ville, lat, lon). Remplir ce qui est connu avec certitude ; les inconnus restent à `NULL` et sont listés dans le journal.
- [ ] `data/reference/venue_surface.csv` : colonnes `venue_id, season_id, surface, source`. Pré-remplir 2025-2026 depuis le classement APPE LNR (Montauban, Biarritz, Provence Rugby, Mont-de-Marsan, Racing 92 en synthétique) ; autres saisons `unknown` à compléter par l'humain.
- [ ] `data/reference/test_windows.csv` : `window_id, label, start_date, end_date, type` (six_nations, autumn, summer, rwc) de 2013-14 à 2026-27.
- [ ] `data/reference/rules_protection.csv` : régimes de la convention FFR/LNR (`docs/01-data-sources.md` §5).
- [ ] `data/reference/protected_players.csv` : en-têtes seulement (`season_id, player_name, source_url`), rempli par l'humain.
- [ ] `data/reference/opt_out.csv`, `er_overrides.csv` : en-têtes seulement.
- [ ] `src/rugby_risk/reference.py` : chargeurs typés (`positions()`, `competitions()`, `test_windows()`…) avec validation Pandera et cache.
- [ ] `data/reference/README.md` : source, date de mise à jour et responsable de chaque fichier.

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

- [ ] 9 postes, 6 groupes, 2 unités.
- [ ] `test_windows.csv` couvre toutes les saisons de `config/seasons.yaml`.
- [ ] Aucune chaîne de poste en dur ailleurs que dans `positions.csv` (vérifié par un test grep sur `src/`).
- [ ] `make check` vert.

## Journal

