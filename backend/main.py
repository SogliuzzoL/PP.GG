import sqlite3

from dotenv import dotenv_values
from flask import Flask, jsonify, request

config = dotenv_values(".env")

app = Flask(__name__)

@app.route('/')
def home():
    return jsonify({"message": "Welcome to the Flask API!"})

@app.route("/matches", methods=["POST"])
def create_match():
    data = request.json
    return jsonify({"message": "Match created!", "data": data}), 201

app.run(port=config["backend_port"],debug=True)