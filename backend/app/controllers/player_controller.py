from flask import Blueprint, jsonify, request

from backend.app.repositories.player_repository import PlayerRepository
from backend.app.services.player_service import PlayerService

player_bp = Blueprint('player', __name__)
repo = PlayerRepository()
service = PlayerService()


@player_bp.route('/top_players', methods=['GET'])
def get_top():
    limit = int(request.args.get('limit', 10))
    offset = int(request.args.get('offset', 0))
    players = repo.get_top_players(limit, offset)
    return jsonify({"top_players": players})


@player_bp.route('/player_stats', methods=['GET'])
def get_stats():
    riot_id = request.args.get('riot_id')
    if not riot_id:
        return jsonify({"error": "Missing riot_id parameter"}), 400

    profile = service.get_player_profile(riot_id)
    if not profile:
        return jsonify({"error": "Player not found"}), 404

    return jsonify(profile)
