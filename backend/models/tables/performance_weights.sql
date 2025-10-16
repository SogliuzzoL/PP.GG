CREATE TABLE IF NOT EXISTS performance_weights (
    weight_id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL UNIQUE,
    kda_weight REAL NOT NULL,
    gold_weight REAL NOT NULL,
    cs_weight REAL NOT NULL,
    damage_weight REAL NOT NULL,
    win_weight REAL NOT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
