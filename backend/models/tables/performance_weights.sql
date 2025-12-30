CREATE TABLE IF NOT EXISTS performance_weights (
    weight_id INTEGER PRIMARY KEY AUTOINCREMENT,
    role TEXT NOT NULL UNIQUE,
    features_json TEXT NOT NULL,
    weights_json TEXT NOT NULL,
    matrix_P BLOB NOT NULL,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
);