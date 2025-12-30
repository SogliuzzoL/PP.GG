import os
import sqlite3

from backend.config import Config


def migrate():
    db_path = Config.DB_PATH
    if not os.path.exists(db_path):
        print(f"❌ Base de données introuvable à : {db_path}")
        return

    print(f"🔄 Migration de la base de données : {db_path} ...")
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Liste des changements (Table, Ancien Nom, Nouveau Nom)
    renames = [
        # Table matches
        ("matches", "match_date", "created_at"),

        # Table player_match_stats
        ("player_match_stats", "champion", "champion_name"),
        ("player_match_stats", "team", "team_side"),
        ("player_match_stats", "winner", "is_winner"),
        ("player_match_stats", "position", "role"),

        # Table player_skill
        ("player_skill", "skill_mu", "mu"),
        ("player_skill", "skill_sigma", "sigma"),

        # Table player_riot_id_history
        ("player_riot_id_history", "start_date", "changed_at"),
    ]

    try:
        for table, old, new in renames:
            try:
                # Vérifie si l'ancienne colonne existe
                cursor.execute(f"SELECT {old} FROM {table} LIMIT 1")
                print(f"   -> Renommage {table}.{old} vers {new}...")
                cursor.execute(
                    f"ALTER TABLE {table} RENAME COLUMN {old} TO {new}")
            except sqlite3.OperationalError:
                # Colonne déjà renommée ou inexistante
                pass

        conn.commit()
        print("✅ Migration terminée avec succès !")

    except Exception as e:
        print(f"❌ Erreur lors de la migration : {e}")
        conn.rollback()
    finally:
        conn.close()


if __name__ == "__main__":
    migrate()
