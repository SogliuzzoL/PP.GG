import sqlite3


def insert_match(db_path: str, game_duration: int, winner: str) -> int:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO matches (game_duration, winner)
        VALUES (?, ?)
        """,
        (game_duration, winner),
    )
    match_id = cursor.lastrowid

    cursor.close()
    conn.commit()
    conn.close()

    return match_id
