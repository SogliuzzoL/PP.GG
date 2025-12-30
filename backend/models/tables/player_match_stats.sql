CREATE TABLE IF NOT EXISTS player_match_stats (
    stat_id INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id INTEGER,
    player_id INTEGER,
    champion_name TEXT,
    team_side TEXT,
    role TEXT,  -- RENOMMAGE ICI (ex-position)
    is_winner BOOLEAN,
    -- Stats brutes
    kills INTEGER,
    deaths INTEGER,
    assists INTEGER,
    total_team_kills INTEGER,
    cs INTEGER,
    gold_earned INTEGER,
    total_damage_dealt_to_champions INTEGER,
    total_team_damage REAL,
    vision_score INTEGER,
    wards_killed INTEGER,
    vision_wards_bought_in_game INTEGER,
    time_ccing_others INTEGER,
    total_heal_on_teammates INTEGER,
    total_damage_shielded_on_teammates INTEGER,
    total_damage_self_mitigated INTEGER,
    total_heal INTEGER,
    FOREIGN KEY(match_id) REFERENCES matches(match_id),
    FOREIGN KEY(player_id) REFERENCES players(player_id)
);