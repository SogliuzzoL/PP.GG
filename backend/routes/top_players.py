import os

from flask import Request, jsonify
from models.database import top_players as top_players_model


def top_players(request: Request):
    db_path = os.getenv("DB_PATH")
    try:
        offset = int(request.args.get("offset", 0))
        limit = int(request.args.get("limit", 10))
    except ValueError:
        return jsonify({"error": "Invalid offset or limit parameter"}), 400

    players = top_players_model(db_path, offset, limit)

    return jsonify({"top_players": players}), 200
