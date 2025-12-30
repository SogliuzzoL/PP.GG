from flask import Flask, jsonify

from backend.app.utils.db import init_db
from backend.config import Config


def create_app():
    app = Flask(__name__)
    app.config.from_object(Config)

    # Note: L'init DB devrait idéalement être faite hors du cycle de vie de l'app en prod,
    # mais pour le dev, on peut le garder ici ou dans un script séparé.
    init_db()

    # Imports des Blueprints
    from backend.app.controllers.analytics_controller import analytics_bp
    from backend.app.controllers.data_controller import data_bp
    from backend.app.controllers.match_controller import match_bp
    from backend.app.controllers.player_controller import player_bp

    # Enregistrement
    app.register_blueprint(match_bp)
    app.register_blueprint(player_bp)
    app.register_blueprint(analytics_bp)
    app.register_blueprint(data_bp)

    @app.route('/')
    def home():
        return jsonify({"message": "PP.GG Backend Modular v2 is running!"})

    return app
