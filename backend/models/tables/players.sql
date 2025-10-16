CREATE TABLE IF NOT EXISTS players (
    player_id INTEGER PRIMARY KEY AUTOINCREMENT,
    puuid TEXT UNIQUE,
    riot_id TEXT,
    current_riot_id TEXT
);
