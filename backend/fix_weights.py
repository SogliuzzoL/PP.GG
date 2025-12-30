import os
import sqlite3

from backend.config import Config


def fix():
    print(
        f"🔧 Réparation de la table performance_weights dans {Config.DB_PATH}...")

    conn = sqlite3.connect(Config.DB_PATH)
    cursor = conn.cursor()

    try:
        # Tentative d'ajout de la colonne manquante
        cursor.execute(
            "ALTER TABLE performance_weights ADD COLUMN updated_at TIMESTAMP")
        print("✅ Colonne 'updated_at' ajoutée.")

        # On remplit avec une date par défaut
        cursor.execute(
            "UPDATE performance_weights SET updated_at = DATETIME('now')")
        print("✅ Données existantes mises à jour.")

    except sqlite3.OperationalError as e:
        if "duplicate column" in str(e):
            print("ℹ️ La colonne 'updated_at' existe déjà.")
        else:
            print(f"⚠️ Impossible d'ajouter la colonne ({e}).")
            print("♻️ Recréation de la table 'performance_weights'...")

            # Si l'ALTER échoue (vieux SQLite), on drop et on recrée
            cursor.execute("DROP TABLE IF EXISTS performance_weights")
            cursor.execute("""
                CREATE TABLE performance_weights (
                    weight_id INTEGER PRIMARY KEY AUTOINCREMENT,
                    role TEXT NOT NULL UNIQUE,
                    features_json TEXT NOT NULL,
                    weights_json TEXT NOT NULL,
                    matrix_P BLOB NOT NULL,
                    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
                );
            """)
            print("✅ Table recréée à neuf.")

    conn.commit()
    conn.close()
    print("🚀 Terminé. Relance le serveur !")


if __name__ == "__main__":
    fix()
