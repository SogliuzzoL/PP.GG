import sqlite3


def initialize_db(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    tables = ["matches", "player_discord_links", "player_match_stats", "player_riot_id_history", "players"]
    for table in tables:
        with open(f"backend/models/tables/{table}.sql", "r") as f:
            sql_script = f.read()
        cursor.execute(sql_script)
    cursor.close()
    conn.commit()
    conn.close()