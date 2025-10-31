import sqlite3


def create_player(conn: sqlite3.Connection, puuid: str, riot_id: str) -> int:
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO players (puuid, riot_id)
        VALUES (?, ?)
        """,
        (puuid, riot_id),
    )
    player_id = cursor.lastrowid
    cursor.close()
    return player_id


def update_player(conn: sqlite3.Connection, player_id: int, riot_id: str):
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE players
        SET riot_id = ?
        WHERE player_id = ?
        """,
        (riot_id, player_id),
    )
    cursor.close()


def get_player(conn: sqlite3.Connection, puuid: str) -> int | None:
    cursor = conn.cursor()
    request = cursor.execute(
        """
        SELECT player_id FROM players WHERE (puuid = ?)
        """,
        (puuid,),
    )
    row = request.fetchone()
    player_id = None
    if row:
        player_id = row[0]
    cursor.close()
    return player_id
