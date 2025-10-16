CREATE TABLE IF NOT EXISTS player_match_stats (
    stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER,
    player_id INTEGER,
    champion_name TEXT,
    team TEXT,
    position TEXT,
    level INTEGER,
    kills INTEGER,
    deaths INTEGER,
    assists INTEGER,
    creep_score INTEGER,
    gold_earned INTEGER,
    total_damage_dealt_to_champions INTEGER,
    vision_score INTEGER,
    winner BOOLEAN,
    FOREIGN KEY(match_id) REFERENCES matches(match_id),
    FOREIGN KEY(player_id) REFERENCES players(player_id)
);
