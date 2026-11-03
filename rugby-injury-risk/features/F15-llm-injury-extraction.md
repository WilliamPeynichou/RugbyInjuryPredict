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

- [ ] Client LLM minimal `injuries/llm_client.py` : un fournisseur configurable, sortie JSON validée par Pydantic, retries sur JSON invalide (2 max), cache disque par `(doc_id, prompt_version, model)` dans `data/staging/_llm_cache/`.
- [ ] Prompt versionné `injuries/prompts/extract_v1.md` (français), avec consignes : n'extraire que les blessures explicitement mentionnées ; ne rien inventer ; `null` si inconnu ; citation ≤ 200 caractères ; distinguer blessure en match / entraînement / inconnu ; dates relatives résolues avec la date de publication.
- [ ] Schéma de sortie :
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
- [ ] Conversion des durées annoncées (« 6 semaines » → 42, « 4 à 6 semaines » → 28–42, « fin de saison » → `season_ending = true`).
- [ ] Rattachement au joueur : correspondance nom normalisé (F09 `normalize`) + équipe + saison sur `dim_player` / `fact_squad_membership` ; ambigu → `player_id = NULL` + file de revue `data/review/news_player_queue.csv`.
- [ ] Rattachement au match : si `onset_context = match`, match de l'équipe le plus proche avant la date de publication (≤ 7 jours) ; sinon `NULL`.
- [ ] Staging `injury_mentions` : `mention_id, doc_id, player_id, match_id, …, extraction_model, prompt_version, extracted_at`.
- [ ] Suivi des coûts : tokens et coût estimé par run loggés (structlog + petit rapport).
- [ ] Mode `dry_run` : traite 20 documents et affiche le résultat sans écrire.

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

- [ ] Pipeline complet exécutable en `dry_run` sur les fixtures F14 avec le client simulé.
- [ ] Un document déjà traité n'est jamais renvoyé au LLM (cache, test).
- [ ] `make check` vert.

## Journal

