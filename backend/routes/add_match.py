# Fichier : backend/routes/add_match.py

import requests
from dotenv import dotenv_values
from flask import Request, jsonify
from models.database import add_match as db_add_match

config = dotenv_values(".env")


def add_match(request: Request):
    data = request.json
    skills, winner = db_add_match(config["db_path"], data)

    # Webhook Discord
    discord_webhook_url = config["discord_webhook_url"]

    # --- MODIFICATION : Organisation par rôle ---

    # Rôles dans l'ordre d'affichage souhaité
    roles_order = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
    role_emojis = {
        "TOP": "⚔️",
        "JUNGLE": "🌳",
        "MIDDLE": "🧙",
        "BOTTOM": "🏹",
        "UTILITY": "❤️",
    }

    # Dictionnaire pour stocker les joueurs classés par équipe et par rôle
    players_by_team = {
        "top": {role: [] for role in roles_order},
        "bot": {role: [] for role in roles_order},
    }

    # Remplir le dictionnaire
    for player, stats in skills.items():
        entry = (
            f"**{player}**\n"
            f"μ=`{stats['mu']:.2f}` | σ=`{stats['sigma']:.2f}`\n"
            f"Perf. Score: `{stats['normalized_score']:.2f}`\n"
            f"α=`{stats['alpha']:.3f}` | y=`{stats['y']:.2f}`"
        )
        # Normaliser le nom de la position
        position = stats["position"].upper()
        if position == "MID":
            position = "MIDDLE"
        if position == "SUPPORT":
            position = "UTILITY"

        if position in roles_order:
            players_by_team[stats["team"]][position].append(entry)

    # Construire la chaîne de caractères pour chaque équipe
    team_top_value_list = []
    for role in roles_order:
        if players_by_team["top"][role]:
            # Ajouter le titre du rôle (ex: ⚔️ TOP)
            team_top_value_list.append(
                f"**{role_emojis.get(role, '')} {role}**")
            # Ajouter les joueurs de ce rôle
            team_top_value_list.extend(players_by_team["top"][role])

    team_bot_value_list = []
    for role in roles_order:
        if players_by_team["bot"][role]:
            # Ajouter le titre du rôle (ex: ⚔️ TOP)
            team_bot_value_list.append(
                f"**{role_emojis.get(role, '')} {role}**")
            # Ajouter les joueurs de ce rôle
            team_bot_value_list.extend(players_by_team["bot"][role])

    # --- Fin de la modification ---

    # Déterminer le style du message selon le vainqueur
    winner_color = 0x57F287 if winner == "top" else 0x5865F2
    winner_emoji = "🟥" if winner == "top" else "🟦"
    winner_text = "Team Top" if winner == "top" else "Team Bot"

    # Créer l'embed
    embed = {
        "title": f"🏆 New Match Created — {winner_emoji} {winner_text} Wins!",
        "description": "A new match result has been recorded in the database.",
        "color": winner_color,
        "fields": [
            {
                "name": "🟥 Team Top",
                "value": "\n\n".join(team_top_value_list) if team_top_value_list else "No players.",
                "inline": True,
            },
            {
                "name": "🟦 Team Bot",
                "value": "\n\n".join(team_bot_value_list) if team_bot_value_list else "No players.",
                "inline": True,
            },
        ],
        "footer": {"text": "PP.GG"},
    }

    # Envoi sur Discord
    requests.post(discord_webhook_url, json={"embeds": [embed]})

    return jsonify({"message": "Match created!", "winner": winner, "skills": skills}), 201
