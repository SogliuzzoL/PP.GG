import os

from dotenv import dotenv_values
from flask import Flask, jsonify, request
from models.database import initialize_db
from routes.add_match import add_match

config = dotenv_values(".env")

app = Flask(__name__)

# Creation du fichier de base de donnees s'il n'existe pas (et des dossiers parents)
os.makedirs(os.path.dirname(config["db_path"]), exist_ok=True)
initialize_db(config["db_path"])

@app.route('/')
def home():
    return jsonify({"message": "Welcome to PP.GG!"})

@app.route("/add_match", methods=["POST"])
def wrapper_add_match():
    return add_match(request)


app.run(port=config["backend_port"],debug=True)