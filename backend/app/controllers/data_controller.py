from flask import Blueprint, jsonify

from backend.app.repositories.weights_repository import WeightsRepository

data_bp = Blueprint('data', __name__)
weights_repo = WeightsRepository()


@data_bp.route('/get_weights', methods=['GET'])
def get_weights():
    weights_data = weights_repo.get_all_weights_formatted()
    return jsonify({"weights": weights_data})
