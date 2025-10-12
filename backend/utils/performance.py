import sqlite3

from dotenv import dotenv_values

config = dotenv_values(".env")

def compute_performance_score(kills: int, 
                              deaths: int, 
                              assists: int, 
                              creep_score: int, 
                              gold_earned: int, 
                              objectives: int,
                              win: bool,
                              role: str,
                              game_duration: int) -> float:
    
    conn = sqlite3.connect(config["db_path"])
    cursor = conn.cursor()
    weights = cursor.execute("SELECT * FROM performance_weights WHERE role = ?", (role,)).fetchone()
    cursor.close()
    conn.close()
    if weights:
        weights = {
            "kda_weight": weights[2],
            "gold_weight": weights[3],
            "cs_weight": weights[4],
            "objectives_weight": weights[5],
            "win_weight": weights[6]
            }
    else:
        weights = {
            "kda_weight": 0.2,
            "gold_weight": 0.2,
            "cs_weight": 0.2,
            "objectives_weight": 0.2,
            "win_weight": 0.2
        }
    print(weights)
    if weights:
        score = 0.0
        score += weights["kda_weight"] * ((kills + assists) / max(1, deaths))
        score += weights["gold_weight"] * (gold_earned / (game_duration / 60))
        score += weights["cs_weight"] * (creep_score / (game_duration / 60))
        score += weights["objectives_weight"] * objectives
        score += weights["win_weight"] * (1 if win else 0)
        return score
    return 0.0