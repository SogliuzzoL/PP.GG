import os

from flask import Request, jsonify
from models.database import get_all_weights as db_get_weights


def get_weights(request: Request):
    db_path = os.getenv("DB_PATH")
    weights = db_get_weights(db_path)
    return jsonify({"weights": weights}), 200
