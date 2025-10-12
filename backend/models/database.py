import sqlite3

from utils.performance import compute_performance_score


def initialize_db(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    tables = [
                "matches", 
                "player_discord_links", 
                "player_match_stats", 
                "player_riot_id_history", 
                "players", 
                "api_tokens", 
                "player_skill", 
                "performance_weights"
              ]
    
    for table in tables:
        with open(f"backend/models/tables/{table}.sql", "r") as f:
            sql_script = f.read()
        cursor.execute(sql_script)
    cursor.close()
    conn.commit()
    conn.close()

def add_match(db_path: str, data: dict):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    # Extract relevant data from the provided dictionary
    players_data = data["allPlayers"]
    events_data = data["events"]
    match_data = data["gameData"]

    # Insert match data into the matches table
    match_request = cursor.execute("INSERT INTO matches (game_mode, map_name, map_terrain, game_duration, events, winner) VALUES (?, ?, ?, ?, ?, ?)", 
                     (
                        match_data["gameMode"],
                        match_data["mapName"],
                        match_data["mapTerrain"],
                        match_data["gameTime"],
                        events_data["Events"].__str__(),
                        match_data["winningTeam"]
                     ))
    
    # Get the match ID of the newly inserted match
    match_id = match_request.lastrowid
    
    # Insert player data into the players table and player_match_stats table
    for player in players_data:
        champion = player["championName"]
        items = player["items"]
        level = player["level"]
        position = player["position"]
        riot_id = player["riotId"]
        username = player["riotIdGameName"]
        runes = player["runes"]
        assists = player["scores"]["assists"]
        creep_score = player["scores"]["creepScore"]
        deaths = player["scores"]["deaths"]
        kills = player["scores"]["kills"]
        skin_name = player["skinName"]
        summoner_spells = player["summonerSpells"]
        team = player["team"]

        gold_earned = 0
        for item in items:
            gold_earned += item["price"]


        player_id = cursor.execute("SELECT player_id FROM players WHERE current_riot_id = ?", (riot_id,)).fetchone()
        if player_id is None:
            player_request = cursor.execute("INSERT INTO players (username, current_riot_id) VALUES (?, ?)", (username, riot_id))
            player_id = player_request.lastrowid
        else:
            player_id = player_id[0]

        cursor.execute("INSERT INTO player_match_stats (match_id, player_id, champion_name, team, position, level, kills, deaths, assists, creep_score, gold_earned, items, runes, summoner_spells, skin_name) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)", 
                       (
                        match_id,
                        player_id,
                        champion,
                        team,
                        position,
                        level,
                        kills,
                        deaths,
                        assists,
                        creep_score,
                        gold_earned,
                        items.__str__(),
                        runes.__str__(),
                        summoner_spells.__str__(),
                        skin_name
                       ))
        player_score = compute_performance_score(
            kills=kills,
            deaths=deaths,
            assists=assists,
            creep_score=creep_score,
            gold_earned=gold_earned,
            objectives=0,
            win=(team == match_data["winningTeam"]),
            role=position,
            game_duration=match_data["gameTime"]
        )
        print(f"Player {username} scored {player_score} points.")
        
    conn.commit()
    cursor.close()
    conn.close()