# Source `espn` — API JSON cachée (non documentée)

Statut : `authorized: false` dans `config/sources.yaml`. Aucun appel réel n'a été fait ; le code
live (`fetch.py`) est bloqué par le garde-fou F03 tant qu'un humain n'a pas autorisé la source.
Formes reprises du dépôt public `transientlunatic/Rugby-Data` (`rugby/scrapers/espn.py`).

## Endpoints

| Usage | URL |
|---|---|
| Matchs d'une ligue/année | `GET https://site.api.espn.com/apis/site/v2/sports/rugby/{leagueId}/scoreboard?dates=YYYY&limit=400` |
| Détail (compositions) | `GET .../rugby/{leagueId}/summary?event={eventId}` |

League ids : Top 14 `270559` (doc de recherche). Six Nations `180659`, Coupe du monde `164205`,
tests `289234` : à confirmer au premier appel autorisé.

## Limites

- Pas d'heure d'entrée/sortie : `minutes_played = NULL`.
- Drapeau `starter` peu fiable : titulaire = maillot 1–15.
- Couverture historique des compositions incomplète.

## Exemple anonymisé

```json
{"header": {"id": "900001", "league": {"name": "Rugby World Cup"},
  "competitions": [{"date": "2023-09-08T19:15Z", "competitors": [
    {"homeAway": "home", "team": {"displayName": "France"}, "score": "27"},
    {"homeAway": "away", "team": {"displayName": "New Zealand"}, "score": "13"}]}]},
 "gameInfo": {"venue": {"fullName": "Stade X"}},
 "rosters": [{"homeAway": "home", "team": {"displayName": "France"},
   "roster": [{"jersey": "1", "athlete": {"id": "a1", "displayName": "Joueur A"}}]}]}
```
