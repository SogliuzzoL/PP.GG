CREATE TABLE IF NOT EXISTS player_skill (
    skill_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL UNIQUE,
    skill_mu REAL NOT NULL,
    skill_sigma REAL NOT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY(player_id) REFERENCES players(player_id)
);
