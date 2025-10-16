import sqlite3

import numpy as np
from models.match import insert_match
from models.performance_weights import get_weights, insert_weights, update_weights
from models.player import create_player, get_player, update_player
from models.player_match_stats import insert_player_match_stats
from utils.performance import RecursiveLeastSquares, compute_performance_score


def initialize_db(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    tables = [
        "matches",
        "player_match_stats",
        "player_riot_id_history",
        "players",
        "api_tokens",
        "player_skill",
        "performance_weights",
    ]

    for table in tables:
        with open(f"backend/models/tables/{table}.sql", "r") as f:
            sql_script = f.read()
        cursor.execute(sql_script)
    cursor.close()
    conn.commit()
    conn.close()


from collections import defaultdict

import numpy as np


def add_match(db_path: str, data: dict):
    # Extraire les informations du match
    game_duration = float(data["gameLength"]) / 60.0  # Durée en minutes
    winner = (
        "bot"
        if data["teams"][0]["isBottomTeam"] and data["teams"][0]["isWinningTeam"]
        or not data["teams"][0]["isBottomTeam"] and not data["teams"][0]["isWinningTeam"]
        else "top"
    )

    # Insérer le match dans la base de données
    match_id = insert_match(db_path, game_duration, winner)

    # Organiser les joueurs par lane
    lane_players = defaultdict(lambda: {"top": None, "bot": None})

    # Traiter chaque joueur et insérer/mettre à jour leurs records
    for team in data["teams"]:
        team_side = "top"
        if team["isBottomTeam"]:
            team_side = "bot"

        for player in team["players"]:
            # Vérifier si le joueur existe, sinon le créer
            player_id = get_player(db_path, player["puuid"])
            riot_id = player["riotIdGameName"] + "#" + player["riotIdTagLine"]
            if not player_id:
                player_id = create_player(db_path, player["puuid"], riot_id)
            else:
                update_player(db_path, player_id, riot_id)

            # Extraire les stats du joueur
            stats = player["stats"]
            champion = player["championName"]
            position = player["detectedTeamPosition"]
            level = int(stats["LEVEL"])
            kills = int(stats["CHAMPIONS_KILLED"])
            deaths = int(stats["NUM_DEATHS"])
            assists = int(stats["ASSISTS"])
            cs = int(stats["MINIONS_KILLED"]) + int(stats["NEUTRAL_MINIONS_KILLED"])
            gold = int(stats["GOLD_EARNED"])
            damage_dealt = int(stats["TOTAL_DAMAGE_DEALT_TO_CHAMPIONS"])
            vision_score = int(stats["VISION_SCORE"])
            is_winner = team_side == winner

            # Insérer les stats du joueur pour ce match
            insert_player_match_stats(
                db_path,
                match_id,
                player_id,
                champion,
                team_side,
                position,
                level,
                kills,
                deaths,
                assists,
                cs,
                gold,
                damage_dealt,
                vision_score,
                is_winner
            )

            # Stocker le joueur dans sa lane
            lane_players[position][team_side] = {
                "player_id": player_id,
                "kills": kills,
                "deaths": deaths,
                "assists": assists,
                "cs": cs,
                "gold": gold,
                "damage_dealt": damage_dealt,
                "vision_score": vision_score,
                "is_winner": is_winner
            }

    # Calculer les PerformanceScores par lane et mettre à jour les poids
    for position, players in lane_players.items():
        if players["top"] and players["bot"]:
            top_player = players["top"]
            bot_player = players["bot"]

            # Récupérer les poids actuels pour cette lane
            weights, matrix_P = get_weights(db_path, position)
            if weights is None:
                weights = {
                    "kda": 1.0,
                    "cs": 1.0,
                    "gold": 1.0,
                    "damage_dealt": 1.0,
                    "vision_score": 1.0
                }
                matrix_P = np.eye(5)
                insert_weights(db_path, position, weights, matrix_P)

            x_top, perf_score_top = compute_performance_score(weights, game_duration,top_player["kills"], top_player["deaths"], top_player["assists"],top_player["cs"], top_player["gold"], top_player["damage_dealt"], top_player["vision_score"])
            x_bot, perf_score_bot = compute_performance_score(weights, game_duration,bot_player["kills"], bot_player["deaths"], bot_player["assists"],bot_player["cs"], bot_player["gold"], bot_player["damage_dealt"], bot_player["vision_score"])

            # Calculer la différence de PerformanceScore centrée en 50
            diff = perf_score_top - perf_score_bot
            win_point_top = 100 if top_player["is_winner"] else 0
            win_point_bot = 100 if bot_player["is_winner"] else 0
            alpha = 1 / (1 + matrix_P.trace() / 10)
            y_top = (50 + (diff / 2)) * alpha + (1 - alpha) * win_point_top
            y_bot = 50 - (diff / 2) * alpha + (1 - alpha) * win_point_bot

            # Mettre à jour les poids pour chaque joueur de la lane
            rls = RecursiveLeastSquares(n_features=6)
            rls.P = matrix_P
            rls.weights = np.array([
                weights["kda"],
                weights["cs"],
                weights["gold"],
                weights["damage_dealt"],
                weights["vision_score"]
            ])

            # Mise à jour pour le joueur TOP
            rls.update(x_top, y_top)

            # Mise à jour pour le joueur BOT
            rls.update(x_bot, y_bot)

            # Extraire les nouveaux poids et la matrice P mise à jour
            new_weights = {
                "kda": float(rls.weights[0]),
                "cs": float(rls.weights[1]),
                "gold": float(rls.weights[2]),
                "damage_dealt": float(rls.weights[3]),
                "vision_score": float(rls.weights[4])
            }
            update_weights(db_path, position, new_weights, rls.P)

            # Mettre à jour le PerformanceScore des joueurs dans la base de données
            # update_player_performance_score(db_path, top_player["player_id"], perf_score_top)
            # update_player_performance_score(db_path, bot_player["player_id"], perf_score_bot)

