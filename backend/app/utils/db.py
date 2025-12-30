import os
import sqlite3

from backend.config import Config


def get_db_connection():
    """Crée une connexion à la base de données SQLite."""
    # On s'assure que le dossier existe AVANT de tenter la connexion
    # C'est plus sûr de le faire ici au cas où on appelle get_db_connection sans passer par init_db
    db_folder = os.path.dirname(Config.DB_PATH)
    if db_folder:
        os.makedirs(db_folder, exist_ok=True)

    conn = sqlite3.connect(Config.DB_PATH)
    conn.row_factory = sqlite3.Row  # Permet d'accéder aux colonnes par nom
    return conn


def init_db():
    """Initialise la base de données avec les schémas SQL."""
    # Le dossier est maintenant créé automatiquement par get_db_connection si besoin
    conn = get_db_connection()
    cursor = conn.cursor()

    # Chemin vers les fichiers SQL
    # On remonte de utils/ -> app/ -> backend/ -> racine -> backend/models/tables
    # Ajustement du chemin pour pointer correctement vers backend/models/tables
    base_dir = os.path.dirname(os.path.dirname(
        os.path.dirname(__file__)))  # backend/
    sql_dir = os.path.join(base_dir, 'models', 'tables')

    tables = [
        "matches", "player_match_stats", "player_riot_id_history", "players",
        "api_tokens", "player_skill", "performance_weights",
    ]

    print(f"Initialisation de la BDD dans : {Config.DB_PATH}")

    for table in tables:
        try:
            file_path = os.path.join(sql_dir, f"{table}.sql")
            with open(file_path, "r") as f:
                cursor.executescript(f.read())
                print(f"✅ Table {table} vérifiée/créée.")
        except FileNotFoundError:
            print(f"⚠️ Fichier SQL introuvable : {file_path}")
        except Exception as e:
            print(f"❌ Erreur init {table}: {e}")

    conn.commit()
    conn.close()
