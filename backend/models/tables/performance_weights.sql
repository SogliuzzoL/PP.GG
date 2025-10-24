CREATE TABLE IF NOT EXISTS performance_weights (
    weight_id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL UNIQUE,
    kda_weight REAL NOT NULL,
    cs_weight REAL NOT NULL,
    gold_weight REAL NOT NULL,
    damage_weight REAL NOT NULL,
    vision_weight REAL NOT NULL,
    cc_weight REAL NOT NULL,
    healt_weight REAL NOT NULL,
    shield_weight REAL NOT NULL,
    damage_taken_weight REAL NOT NULL,
    matrix_P TEXT NOT NULL,
    last_updated TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);
