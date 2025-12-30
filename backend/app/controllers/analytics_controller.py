from flask import Blueprint, jsonify, send_file

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
