import sqlite3


def insert_player_match_stats(
    cursor: sqlite3.Cursor,
    match_id: int,
    player_id: int,
    champion: str,
    team: str,
    position: str,
    winner: bool,
    kills: int,
    deaths: int,
    assists: int,
    total_team_kills: int,
    cs: int,
    gold_earned: int,
    total_damage_dealt_to_champions: int,
    total_team_damage: float,
    vision_score: int,
    wards_killed: int,
    vision_wards_bought_in_game: int,
    time_ccing_others: int,
    total_heal_on_teammates: int,
    total_damage_shielded_on_teammates: int,
    total_damage_self_mitigated: int,
    total_heal: int
):
    """
    Insère les statistiques brutes d'un joueur pour un match.
    """
    cursor.execute(
        """
        INSERT INTO player_match_stats (
            match_id, player_id, champion, team, position, winner,
            kills, deaths, assists, total_team_kills, cs, gold_earned,
            total_damage_dealt_to_champions, total_team_damage,
            vision_score, wards_killed, vision_wards_bought_in_game,
            time_ccing_others, total_heal_on_teammates,
            total_damage_shielded_on_teammates,
            total_damage_self_mitigated, total_heal
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            match_id, player_id, champion, team, position, winner,
            kills, deaths, assists, total_team_kills, cs, gold_earned,
            total_damage_dealt_to_champions, total_team_damage,
            vision_score, wards_killed, vision_wards_bought_in_game,
            time_ccing_others, total_heal_on_teammates,
            total_damage_shielded_on_teammates,
            total_damage_self_mitigated, total_heal
        )
    )
