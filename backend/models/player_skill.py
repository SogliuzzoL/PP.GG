import sqlite3


def insert_player_skill(conn: sqlite3.Connection, player_id: int, mu: float, sigma: float):
    cursor = conn.cursor()
    cursor.execute(
        """
        INSERT INTO player_skill (player_id, skill_mu, skill_sigma)
        VALUES (?, ?, ?)
        """,
        (player_id, mu, sigma),
    )
    cursor.close()


def update_player_skill(conn: sqlite3.Connection, player_id: int, mu: float, sigma: float):
    cursor = conn.cursor()
    cursor.execute(
        """
        UPDATE player_skill
        SET skill_mu = ?, skill_sigma = ?
        WHERE player_id = ?
        """,
        (mu, sigma, player_id),
    )
    cursor.close()


def get_player_skill(conn: sqlite3.Connection, player_id: int) -> tuple[float, float] | None:
    cursor = conn.cursor()
    request = cursor.execute(
        """
        SELECT skill_mu, skill_sigma FROM player_skill WHERE (player_id = ?)
        """,
        (player_id,),
    )
    row = request.fetchone()
    skill = None
    if row:
        skill = (row[0], row[1])
    cursor.close()
    return skill
