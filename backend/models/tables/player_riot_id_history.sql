CREATE TABLE IF NOT EXISTS player_riot_id_history (
    history_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER,
    riot_id TEXT,
    start_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    end_date TIMESTAMP NULL,
    FOREIGN KEY(player_id) REFERENCES players(player_id)
);
