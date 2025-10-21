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

    # Séparer les joueurs par équipe
    team_top = []
    team_bot = []
    for player, (mu, sigma, team) in skills.items():
        entry = f"**{player}**\nμ = `{mu:.2f}` | σ = `{sigma:.2f}`"
        if team == "top":
            team_top.append(entry)
        elif team == "bot":
            team_bot.append(entry)

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
                "value": "\n".join(team_top) if team_top else "No players.",
                "inline": True,
            },
            {
                "name": "🟦 Team Bot",
                "value": "\n".join(team_bot) if team_bot else "No players.",
                "inline": True,
            },
        ],
        "footer": {"text": "Linker Match System"},
    }

    # Envoi sur Discord
    requests.post(discord_webhook_url, json={"embeds": [embed]})

    return jsonify({"message": "Match created!", "winner": winner, "skills": skills}), 201
