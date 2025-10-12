from flask import Request, jsonify


def add_match(request: Request):
    data = request.json
    return jsonify({"message": "Match created!", "data": data}), 201