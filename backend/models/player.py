import sqlite3


def create_player(db_path: str, puuid: str, riot_id: str) -> int:
    conn = sqlite3.connect(db_path)
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
    conn.commit()
    conn.close()

    return player_id


def update_player(db_path: str, player_id: int, riot_id: str):
    conn = sqlite3.connect(db_path)
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
    conn.commit()
    conn.close()


def get_player(db_path: str, puuid: str) -> int | None:
    conn = sqlite3.connect(db_path)
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
    conn.commit()
    conn.close()

    return player_id