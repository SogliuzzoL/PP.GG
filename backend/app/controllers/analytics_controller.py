from flask import Blueprint, jsonify, request, send_file

from backend.app.services.analytics_service import AnalyticsService

analytics_bp = Blueprint('analytics', __name__)
service = AnalyticsService()


@analytics_bp.route('/meta/<role>', methods=['GET'])
def get_meta(role):
    result = service.get_meta_analysis(role)
    if "error" in result:
        return jsonify(result), 400
    return jsonify(result)


@analytics_bp.route('/correlation_matrix/<role>', methods=['GET'])
def get_matrix(role):
    try:
        image_buf = service.get_correlation_matrix_image(role)
        return send_file(image_buf, mimetype='image/png', max_age=0)
    except ValueError as e:
        return jsonify({"error": str(e)}), 400
    except Exception as e:
        return jsonify({"error": f"Internal Error: {e}"}), 500


@analytics_bp.route('/personal_meta', methods=['GET'])
def personal_meta():
    riot_id = request.args.get('riot_id')
    role = request.args.get('role')

    if not riot_id or not role:
        return jsonify({"error": "Paramètres manquants"}), 400

    result = service.get_personal_shap_analysis(riot_id, role)

    if "error" in result:
        return jsonify(result), 400

    return jsonify(result), 200


@analytics_bp.route('/match_analysis/<match_id>', methods=['GET'])
def match_analysis(match_id):
    riot_id = request.args.get('riot_id')
    if not riot_id:
        return jsonify({"error": "Riot ID manquant"}), 400

    try:
        # On passe le match_id et le riot_id au service
        result = service.analyze_specific_match(match_id, riot_id)
        if "error" in result:
            return jsonify(result), 400
        return jsonify(result)
    except Exception as e:
        return jsonify({"error": f"Erreur interne: {str(e)}"}), 500
