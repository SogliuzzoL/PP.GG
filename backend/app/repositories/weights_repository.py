import json

import numpy as np

from backend.app.utils.db import get_db_connection


class WeightsRepository:
    def get_weights(self, role):
        conn = get_db_connection()
        row = conn.execute(
            "SELECT features_json, weights_json, matrix_P FROM performance_weights WHERE role = ?", (role,)).fetchone()
        conn.close()

        if not row:
            return None, None, None

        features = json.loads(row['features_json'])
        weights = json.loads(row['weights_json'])
        # Reconstruction de la matrice P depuis le blob binaire
        n = len(features)
        matrix_P = np.frombuffer(
            row['matrix_P'], dtype=np.float64).reshape((n, n))

        return features, weights, matrix_P

    def save_weights(self, role, features, weights, matrix_P):
        conn = get_db_connection()
        features_json = json.dumps(features)
        weights_json = json.dumps(weights)
        matrix_bytes = matrix_P.tobytes()

        # UPSERT
        exists = conn.execute(
            "SELECT 1 FROM performance_weights WHERE role = ?", (role,)).fetchone()
        if exists:
            conn.execute(
                "UPDATE performance_weights SET features_json=?, weights_json=?, matrix_P=?, updated_at=DATETIME('now') WHERE role=?",
                (features_json, weights_json, matrix_bytes, role)
            )
        else:
            conn.execute(
                "INSERT INTO performance_weights (role, features_json, weights_json, matrix_P, updated_at) VALUES (?, ?, ?, ?, DATETIME('now'))",
                (role, features_json, weights_json, matrix_bytes)
            )
        conn.commit()
        conn.close()

    def get_all_weights_formatted(self):
        conn = get_db_connection()
        rows = conn.execute(
            "SELECT role, weights_json FROM performance_weights").fetchall()
        conn.close()
        return {row['role']: json.loads(row['weights_json']) for row in rows}
