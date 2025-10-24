import sqlite3

import numpy as np
from config.weights import activate_weights, all_weights


def get_weights(db_path: str, position: str) -> dict | None:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    request = cursor.execute(
        """
        SELECT * FROM performance_weights WHERE (role = ?)
        """,
        (position,),
    )

    row = request.fetchone()
    weights = None
    matrix_P = None

    if row:
        weights = {key: row[i] for i, key in zip(
            range(2, 11), all_weights) if key in activate_weights[position]}
        n = len(activate_weights[position])
        matrix_P = np.frombuffer(row[11], dtype=np.float64).reshape((n, n))

    cursor.close()
    conn.commit()
    conn.close()

    return weights, matrix_P


def insert_weights(db_path: str, position: str, weights: dict, maxtrix_P: np.ndarray):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO performance_weights (role, kda_weight, cs_weight, gold_weight, damage_weight, 
        vision_weight, cc_weight, healt_weight, shield_weight, damage_taken_weight, matrix_P)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            position,
            weights.get("kda", 0),
            weights.get("cs", 0),
            weights.get("gold", 0),
            weights.get("damage_dealt", 0),
            weights.get("vision_score", 0),
            weights.get("cc_score", 0),
            weights.get("healing_done", 0),
            weights.get("shield_amount", 0),
            weights.get("damage_taken", 0),
            maxtrix_P
        ),
    )

    cursor.close()
    conn.commit()
    conn.close()


def update_weights(db_path: str, position: str, weights: dict, matrix_P: np.ndarray):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        UPDATE performance_weights
        SET kda_weight = ?, cs_weight = ?, gold_weight = ?, damage_weight = ?, vision_weight = ?,
        cc_weight = ?, healt_weight = ?, shield_weight = ?, damage_taken_weight = ?, matrix_P = ?
        WHERE role = ?
        """,
        (
            weights.get("kda", 0),
            weights.get("cs", 0),
            weights.get("gold", 0),
            weights.get("damage_dealt", 0),
            weights.get("vision_score", 0),
            weights.get("cc_score", 0),
            weights.get("healing_done", 0),
            weights.get("shield_amount", 0),
            weights.get("damage_taken", 0),
            matrix_P,
            position,
        ),
    )

    cursor.close()
    conn.commit()
    conn.close()
