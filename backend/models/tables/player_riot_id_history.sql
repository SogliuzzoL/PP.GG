CREATE TABLE IF NOT EXISTS player_riot_id_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER,
    riot_id TEXT,
    changed_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(player_id) REFERENCES players(player_id)
);