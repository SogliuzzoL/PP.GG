from flask import Blueprint, jsonify, request

from backend.app.services.match_service import MatchService

match_bp = Blueprint('match', __name__)
service = MatchService()


@match_bp.route('/add_match', methods=['POST'])
def add_match():
    data = request.json
    if not data or 'teams' not in data:
        return jsonify({"error": "Invalid data"}), 400

    try:
        result = service.process_match(data)
        return jsonify(result), 200
    except Exception as e:
        print(f"Error processing match: {e}")
        return jsonify({"error": str(e)}), 500
