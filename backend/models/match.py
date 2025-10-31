import sqlite3


def insert_match(conn: sqlite3.Connection, game_duration: float, winner: str) -> int:
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
    return match_id
