# F15 — Extraction LLM des blessures

| Champ | Valeur |
|---|---|
| Phase | 3 |
| Dépendances | F14, F09 |
| Estimation | L |
| Docs de référence | `docs/04-data-model.md` (`fact_injury_event`), `docs/07-legal-rgpd.md` §2–3 |

## Objectif

Transformer chaque document presse filtré en mentions de blessure structurées (joueur, date, zone, type, durée annoncée, citation courte), rattachées à un `player_id`.

## Contexte

Un LLM avec sortie structurée est plus robuste que des règles sur des textes variés. La qualité est mesurée sur un jeu annoté (F16). Le modèle est configurable (`LLM_MODEL`) et les appels sont mis en cache pour ne jamais payer deux fois le même document.

## Périmètre

- [x] Client LLM minimal `injuries/llm_client.py` : un fournisseur configurable, sortie JSON validée par Pydantic, retries sur JSON invalide (2 max), cache disque par `(doc_id, prompt_version, model)` dans `data/staging/_llm_cache/`.
- [x] Prompt versionné `injuries/prompts/extract_v1.md` (français), avec consignes : n'extraire que les blessures explicitement mentionnées ; ne rien inventer ; `null` si inconnu ; citation ≤ 200 caractères ; distinguer blessure en match / entraînement / inconnu ; dates relatives résolues avec la date de publication.
- [x] Schéma de sortie :
  ```python
  class InjuryMention(BaseModel):
      player_name: str
      team_name: str | None
      onset_date: date | None
      onset_context: Literal["match", "training", "unknown"]
      opponent_or_match_hint: str | None
      body_region: BodyRegion | None  # vocabulaire de docs/04-data-model.md
      injury_type: InjuryType | None
      is_concussion: bool
      announced_duration_days_min: int | None
      announced_duration_days_max: int | None
      season_ending: bool
      return_mentioned: bool
      quote: str = Field(max_length=200)


  class ExtractionResult(BaseModel):
      mentions: list[InjuryMention]
  ```
- [x] Conversion des durées annoncées (« 6 semaines » → 42, « 4 à 6 semaines » → 28–42, « fin de saison » → `season_ending = true`).
- [x] Rattachement au joueur : correspondance nom normalisé (F09 `normalize`) + équipe + saison sur `dim_player` / `fact_squad_membership` ; ambigu → `player_id = NULL` + file de revue `data/review/news_player_queue.csv`.
- [x] Rattachement au match : si `onset_context = match`, match de l'équipe le plus proche avant la date de publication (≤ 7 jours) ; sinon `NULL`.
- [x] Staging `injury_mentions` : `mention_id, doc_id, player_id, match_id, …, extraction_model, prompt_version, extracted_at`.
- [x] Suivi des coûts : tokens et coût estimé par run loggés (structlog + petit rapport).
- [x] Mode `dry_run` : traite 20 documents et affiche le résultat sans écrire.

## Hors périmètre

- Fusion avec les autres signaux et score final (F16).

## Spécification technique

- Vocabulaires `BodyRegion`, `InjuryType` : enums Python générés depuis `docs/04-data-model.md` (une seule définition dans `injuries/vocab.py`).
- Les noms de joueurs passent par le LLM : la clé API et le fournisseur doivent être validés par l'humain (journal) au regard de `docs/07-legal-rgpd.md`.

## Fichiers

| Fichier | Action |
|---|---|
| `src/rugby_risk/injuries/{llm_client,extract,durations,link,vocab}.py` | créer |
| `src/rugby_risk/injuries/prompts/extract_v1.md` | créer |
| `orchestration/assets/injury_mentions.py` | créer |

## Tests

- `tests/unit/injuries/test_durations.py` — 12 expressions françaises de durée.
- `tests/unit/injuries/test_extract.py` — client LLM simulé (réponses JSON figées) : validation, retry sur JSON invalide, cache utilisé au second appel.
- `tests/unit/injuries/test_link.py` — rattachement joueur et match, cas ambigu → file de revue.
- Aucun appel réel au LLM dans les tests.

## Critères d'acceptation

- [x] Pipeline complet exécutable en `dry_run` sur les fixtures F14 avec le client simulé.
- [x] Un document déjà traité n'est jamais renvoyé au LLM (cache, test).
- [x] `make check` vert.

## Journal

- 2026-11-05 — Livré sur branche `feat/F15-llm-injury-extraction`.
  - **Fournisseur : client OpenAI-compatible minimal (httpx)** — `LLM_BASE_URL` /
    `LLM_MODEL` / `LLM_API_KEY` (settings). Couvre OpenAI, Mistral et tout endpoint
    compatible sans dépendance supplémentaire. Le client **lève une erreur sans clé** :
    ni fournisseur ni clé n'est validé par l'humain à ce jour (docs/07) — aucun appel réel
    n'est donc possible, conformément au périmètre.
  - Cache disque `data/staging/_llm_cache/<sha256(doc_id|prompt_version|model)>.json` ;
    testé : un second appel ne re-appelle pas `_chat`.
  - `run_extraction` reçoit `extract_json` en injection : les tests utilisent un stub à
    réponses figées, aucun appel réel. Un document en échec (JSON invalide après retries,
    schéma Pydantic rejeté) est journalisé et sauté, sans stopper le lot.
  - Prompt `extract_v1.md` : remplissage par `.replace()` (le modèle JSON d'exemple
    contient des accolades qui cassent `str.format`).
  - Entrée documents : entité staging `news_doc` (contrat F14, qui n'a pas laissé de code —
    voir souci T9). L'asset `injury_mentions` est un no-op propre tant que
    `data/staging/news_doc/` est absent.
  - Coût : tokens prompt/complétion loggés (structlog) + rapport `data/staging/_reports/
    llm_usage.md`. Le coût estimé reste 0,0 tant que les taux du fournisseur ne sont pas
    configurés (décision humaine au moment du choix du fournisseur).
  - Vocabulaires : enums Python dans `injuries/vocab.py`, **test de concordance avec
    docs/04-data-model.md** (unique définition côté code, la doc est vérifiée).
  - `injury_mention` est une entité staging validée (Pandera) ; `fact_injury_event` (mart)
    reste du ressort de F16 (fusion des signaux).
  - Écart : la file de revue `write_review_queue` a son chemin par défaut lié à l'import
    (`data/review/news_player_queue.csv`) ; la surcharge par monkeypatch ne s'applique pas
    au défaut. Sans objet en run réel (chemin voulu), à refactorer si un test l'exige.

