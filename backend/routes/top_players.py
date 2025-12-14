from dotenv import dotenv_values
from flask import Request, jsonify
from models.database import top_players as top_players_model

config = dotenv_values(".env")


def top_players(request: Request):
    db_path = config.get("db_path")
    try:
        offset = int(request.args.get("offset", 0))
        limit = int(request.args.get("limit", 10))
        time_limit = int(request.args.get("time_limit", 15))  # in days
    except ValueError:
        return jsonify({"error": "Invalid offset or limit parameter"}), 400

    print(db_path)
    players = top_players_model(db_path, offset, limit, time_limit)

    return jsonify({"top_players": players}), 200
