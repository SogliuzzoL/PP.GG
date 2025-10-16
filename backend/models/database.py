import sqlite3

from utils.performance import compute_performance_score


def initialize_db(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    tables = [
        "matches",
        "player_match_stats",
        "player_riot_id_history",
        "players",
        "api_tokens",
        "player_skill",
        "performance_weights",
    ]

    for table in tables:
        with open(f"backend/models/tables/{table}.sql", "r") as f:
            sql_script = f.read()
        cursor.execute(sql_script)
    cursor.close()
    conn.commit()
    conn.close()


def add_match(db_path: str, data: dict):
    game_duration = int(data["gameLength"] / 60)
    winner = (
        "bot"
        if data["teams"][0]["isBottomTeam"]
        and data["teams"][0]["isWinningTeam"]
        or not data["teams"][0]["isBottomTeam"]
        and not data["teams"][0]["isWinningTeam"]
        else "top"
    )
    match_id = insert_match(db_path, game_duration, winner)

    for team in data["teams"]:
        for player in team["players"]:
            player_id = get_player(db_path, player["puuid"])
            riot_id = player["riotIdGameName"] + "#" + player["riotIdTagLine"]
            if player_id:
                update_player(db_path, player_id, riot_id)
            else:
                player_id = create_player(db_path, player["puuid"], riot_id)


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
        WHERE id = ?
        """,
        (riot_id, player_id),
    )

    cursor.close()
    conn.commit()
    conn.close()


def get_player(db_path: str, puuid: str) -> int:
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        SELECT * FROM players WHERE (puuid = ?)
        """,
        (puuid,),
    )
    player_id = cursor.lastrowid

    cursor.close()
    conn.commit()
    conn.close()

    return player_id


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
