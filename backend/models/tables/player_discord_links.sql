CREATE TABLE IF NOT EXISTS player_discord_links (
    link_id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER,
    discord_id TEXT UNIQUE,
    FOREIGN KEY(player_id) REFERENCES players(player_id)
);
