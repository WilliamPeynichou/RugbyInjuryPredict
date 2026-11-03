# Source `worldrugby` — API pulselive (non documentée)

Statut : `authorized: false` dans `config/sources.yaml`. Aucun appel réel n'a été fait ; le code
live (`fetch.py`) est bloqué par le garde-fou F03 tant qu'un humain n'a pas autorisé la source.
Les formes ci-dessous sont reprises du dépôt public `bpcsaund/rugby-analytics`
(`ingestion/wr_national_teams_scraper.py`), cité par le document de recherche.

## Endpoints

| Usage | URL |
|---|---|
| Liste des matchs | `GET https://api.wr-rims-prod.pulselive.com/rugby/v3/match?sport=mru&states=C&sort=asc&page=0&pageSize=100&startDate=YYYY-MM-DD&endDate=YYYY-MM-DD` |
| Résumé (compositions) | `GET .../rugby/v3/match/{matchAltId}/summary` |
| Chronologie (entrées/sorties) | `GET .../rugby/v3/match/{matchAltId}/timeline` |

`sport=mru` = rugby à XV masculin (exclut 7 et féminin). Filtre `TRACKED_NATIONS` dans `fetch.py`.

## Exemple anonymisé

```json
// summary
{"match": {"matchId": "wr-0001", "matchAltId": "alt-0001", "competition": "Six Nations 2024",
  "status": "C", "time": {"millis": 1706904000000, "label": "2024-02-02"},
  "venue": {"name": "Stade X", "city": "Ville", "country": "France"},
  "teams": [{"id": "42", "name": "France"}, {"id": "34", "name": "Ireland"}], "scores": [17, 38]},
 "teams": [{"teamList": {"list": [{"number": "1", "player": {"id": "p1", "name": {"display": "Joueur A"}}}]}}, {"...": "..."}]}
// timeline
{"timeline": [{"type": "Sub Off", "teamIndex": 0, "playerId": "p1", "time": {"secs": 3000}}]}
```

Types d'événements utilisés : `Sub On`, `Sub Off`, `IR` et `HIAO` (bascule d'état), `Red Card`
(sortie définitive), `Yellow Card` (comptage seulement).
