from flask import Blueprint, jsonify, request

from backend.app.repositories.player_repository import PlayerRepository
from backend.app.services.player_service import PlayerService
from backend.app.services.team_service import TeamService

player_bp = Blueprint('player', __name__)
repo = PlayerRepository()
service = PlayerService()
team_service = TeamService()


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


@player_bp.route('/balance_teams', methods=['POST'])
def balance():
    data = request.json
    players = data.get('players', [])

    if not players:
        return jsonify({"error": "Aucune liste de joueurs fournie"}), 400

    result = team_service.balance_teams(players)
    if "error" in result:
        return jsonify(result), 400

    return jsonify(result)
