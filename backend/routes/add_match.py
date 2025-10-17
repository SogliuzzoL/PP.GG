from dotenv import dotenv_values
from flask import Request, jsonify
from models.database import add_match as db_add_match

config = dotenv_values(".env")


def add_match(request: Request):
    data = request.json
    skills = db_add_match(config["db_path"], data)
    return jsonify({"message": "Match created!", "skills": skills}), 201