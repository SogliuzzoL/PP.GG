CREATE TABLE IF NOT EXISTS matches (
    match_id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_mode TEXT,
    map_name TEXT,
    map_terrain TEXT,
    game_duration REAL,
    events TEXT,
    winner TEXT,
    match_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);