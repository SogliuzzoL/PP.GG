import sqlite3


def insert_player_match_stats(db_path: str,
                              match_id: int,
                              player_id: int,
                              champion: str,
                              team: str,
                              position: str,
                              level: int,
                              kills: int,
                              deaths: int,
                              assists: int,
                              cs: int,
                              gold: int,
                              damage_dealt: int,
                              vision_score: int,
                              cc_score: int,
                              healing_done: int,
                              shield_amount: int,
                              damage_taken: int,
                              is_winner: bool,
                              ):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    cursor.execute(
        """
        INSERT INTO player_match_stats (
            match_id, player_id, champion, team, position, level,
            kills, deaths, assists, creep_score, gold_earned,
            damage_dealt, vision_score, cc_score, healing_done, 
            shield_amount, damage_taken, winner
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            match_id, player_id, champion, team, position, level,
            kills, deaths, assists, cs, gold,
            damage_dealt, vision_score, cc_score,
            healing_done, shield_amount, damage_taken, is_winner
        )
    )

    cursor.close()
    conn.commit()
    conn.close()
