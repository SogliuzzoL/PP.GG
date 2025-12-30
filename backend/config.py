import os

from dotenv import load_dotenv

# Charger le .env depuis la racine du projet
basedir = os.path.abspath(os.path.dirname(__file__))
root_dir = os.path.join(basedir, '..')  # Remonte à la racine PP.GG
load_dotenv(os.path.join(root_dir, '.env'))


class Config:
    DB_PATH = os.getenv('db_path', 'data/db.sqlite3')
    BACKEND_PORT = int(os.getenv('backend_port', 5000))
    DISCORD_WEBHOOK_URL = os.getenv('discord_webhook_url')
    # Assure que le chemin de la DB est absolu si nécessaire ou relatif correct
    if not os.path.isabs(DB_PATH):
        DB_PATH = os.path.join(root_dir, DB_PATH)
