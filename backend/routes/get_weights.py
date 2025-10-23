from dotenv import dotenv_values
from flask import Request, jsonify
from models.database import get_all_weights as db_get_weights

config = dotenv_values(".env")


def get_weights(request: Request):
    db_path = config.get("db_path")
    weights = db_get_weights(db_path)
    return jsonify({"weights": weights}), 200
