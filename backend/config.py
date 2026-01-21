import os

from dotenv import load_dotenv

# Charger le .env depuis la racine du projet
basedir = os.path.abspath(os.path.dirname(__file__))
root_dir = os.path.join(basedir, '..')  # Remonte à la racine PP.GG
load_dotenv(os.path.join(root_dir, '.env'))


class Config:
    DB_PATH = os.getenv('DB_PATH', 'data/db.sqlite3')
    BACKEND_PORT = int(os.getenv('BACKEND_PORT', 5000))
    DISCORD_WEBHOOK_URL = os.getenv('DISCORD_WEBHOOK_URL')
    # Assure que le chemin de la DB est absolu si nécessaire ou relatif correct
    if not os.path.isabs(DB_PATH):
        DB_PATH = os.path.join(root_dir, DB_PATH)

    FEATURES = {
        "kda": "KDA", "kill_participation": "KP (%)", "cs_per_min": "CS/min",
        "gold_per_min": "Gold/min", "damage_dealt_per_min": "DPM",
        "vision_score_per_min": "Vis/min", "vision_control_per_min": "Vis. Ctrl/min",
        "cc_score_per_min": "CC/min", "healing_on_teammates_per_min": "Heal/min",
        "effective_tanking_per_min": "Tank/min", "team_damage_percentage": "Dmg%",
        "kills_per_min": "Kills/min", "deaths_per_min": "Deaths/min", "assists_per_min": "Assists/min"
    }
