Tu extrais les mentions de blessure d'un article de presse rugby. Réponds UNIQUEMENT avec un
objet JSON valide, sans texte avant ou après.

Règles :
- N'extraire que les blessures explicitement mentionnées dans le texte. Ne rien inventer.
- `null` pour toute information absente ou incertaine.
- Chaque citation (`quote`) est un extrait exact du texte, ≤ 200 caractères.
- `onset_context` : "match" si la blessure est survenue lors d'un match, "training" si lors
  d'un entraînement, sinon "unknown".
- `body_region` et `injury_type` : uniquement les valeurs des listes ci-dessous.
- `is_concussion` : vrai seulement si une commotion cérébrale est explicitement mentionnée.
- `announced_duration_text` : la durée annoncée telle quelle (« 6 semaines », « 4 à 6
  semaines », « fin de saison », « quelques jours »), sinon `null`.
- `season_ending` : vrai si l'article dit que la saison est terminée pour le joueur.
- `return_mentioned` : vrai si un retour (date ou « disponible pour ») est mentionné.
- Résous les dates relatives avec la date de publication de l'article.
- `onset_date` : date de survenue de la blessure (AAAA-MM-JJ), sinon `null`.
- `opponent_or_match_hint` : adversaire ou identifiant du match si mentionné, sinon `null`.

body_region : head, neck, shoulder, arm, trunk, hip_groin, thigh, knee, lower_leg, ankle,
foot, other.
injury_type : concussion, ligament, muscle, fracture, contusion, tendon, other, unknown.

Format de réponse :
{
  "mentions": [
    {
      "player_name": "Prénom Nom", "team_name": null, "onset_date": null,
      "onset_context": "unknown", "opponent_or_match_hint": null, "body_region": null,
      "injury_type": null, "is_concussion": false, "announced_duration_text": null,
      "season_ending": false, "return_mentioned": false, "quote": "..."
    }
  ]
}

Date de publication de l'article : {published_at}
Texte de l'article :
{article}
