import json
import sqlite3

import numpy as np


def get_weights_for_role(conn: sqlite3.Connection, role: str):
    cursor = conn.cursor()
    cursor.execute(
        "SELECT features_json, weights_json, matrix_P FROM performance_weights WHERE role = ?", (role,))
    row = cursor.fetchone()
    cursor.close()

    if not row:
        return None, None, None

    features = json.loads(row[0])
    weights = json.loads(row[1])
    n_features = len(features)
    try:
        matrix_P = np.frombuffer(row[2], dtype=np.float64).reshape(
            (n_features, n_features))
    except (ValueError, TypeError):
        print(
            f"Erreur de format de la matrice P pour {role}. Réinitialisation.")
        matrix_P = np.eye(n_features) * 1000  # Fallback

    return features, weights, matrix_P


def save_weights_for_role(conn: sqlite3.Connection, role: str, features: list, weights: dict, matrix_P: np.ndarray):
    cursor = conn.cursor()

    features_json = json.dumps(features)
    weights_json = json.dumps(weights)
    matrix_P_blob = matrix_P.tobytes()

    cursor.execute(
        """
        INSERT OR REPLACE INTO performance_weights (role, features_json, weights_json, matrix_P, last_updated)
        VALUES (?, ?, ?, ?, CURRENT_TIMESTAMP)
        """,
        (role, features_json, weights_json, matrix_P_blob)
    )
    cursor.close()
