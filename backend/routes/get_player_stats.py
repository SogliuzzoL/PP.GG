from dotenv import dotenv_values
from flask import Request, jsonify
from models.player_profile import get_player_profile_data

config = dotenv_values(".env")


def get_player_stats(request: Request):
    db_path = config.get("db_path")
    # Récupérer le riot_id depuis un paramètre d'URL (ex: /player_stats?riot_id=MonPseudo#EUW)
    riot_id = request.args.get("riot_id")

    if not riot_id:
        return jsonify({"error": "Le paramètre 'riot_id' est requis"}), 400

    player_data = get_player_profile_data(db_path, riot_id)

    if not player_data:
        return jsonify({"error": "Joueur non trouvé"}), 404

    return jsonify(player_data), 200
