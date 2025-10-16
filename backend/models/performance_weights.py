import sqlite3

import numpy as np


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
    keys = ["kda", "cs", "gold", "damage_dealt", "vision_score"]
    if row:
        weights = {key: row[i] for i, key in zip(range(2, 7), keys)}
        matrix_P = np.frombuffer(row[7], dtype=np.float64).reshape((5, 5))

    cursor.close()
    conn.commit()
    conn.close()

    return weights, matrix_P

def insert_weights(db_path: str, position: str, weights: dict, maxtrix_P: np.ndarray):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO performance_weights (role, kda_weight, cs_weight, gold_weight, damage_weight, vision_weight, matrix_P)
        VALUES (?, ?, ?, ?, ?, ?, ?)
        """,
        (
            position,
            weights["kda"],
            weights["cs"],
            weights["gold"],
            weights["damage_dealt"],
            weights["vision_score"],
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
        SET kda_weight = ?, cs_weight = ?, gold_weight = ?, damage_weight = ?, vision_weight = ?, matrix_P = ?
        WHERE role = ?
        """,
        (
            weights.get("kda", 0.5),
            weights.get("cs", 0.5),
            weights.get("gold", 0.05),
            weights.get("damage_dealt", 0.05),
            weights.get("vision_score", 0.5),
            matrix_P,
            position,
        ),
    )

    cursor.close()
    conn.commit()
    conn.close()