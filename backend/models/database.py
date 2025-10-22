import sqlite3
from collections import defaultdict

import numpy as np
from models.match import insert_match
from models.performance_weights import get_weights, insert_weights, update_weights
from models.player import create_player, get_player, update_player
from models.player_match_stats import insert_player_match_stats
from models.player_skill import (
    get_player_skill,
    insert_player_skill,
    update_player_skill,
)
from utils.performance import (
    KalmanSkillFilter,
    RecursiveLeastSquares,
    compute_performance_score,
)


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
            cs = int(stats["MINIONS_KILLED"]) + \
                int(stats["NEUTRAL_MINIONS_KILLED"])
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
                "riot_id": riot_id,
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
    skills = {}
    for position, players in lane_players.items():
        if players["top"] and players["bot"]:
            top_player = players["top"]
            bot_player = players["bot"]

            # Récupérer les poids actuels pour cette lane
            weights, matrix_P = get_weights(db_path, position)
            if weights is None:
                weights = {
                    "kda": 0.1,
                    "cs": 0.1,
                    "gold": 0.1,
                    "damage_dealt": 0.1,
                    "vision_score": 0.1
                }
                matrix_P = np.eye(5)
                insert_weights(db_path, position, weights, matrix_P)

            x_top, perf_score_top = compute_performance_score(weights, game_duration, top_player["kills"], top_player["deaths"], top_player[
                                                              "assists"], top_player["cs"], top_player["gold"], top_player["damage_dealt"], top_player["vision_score"])
            x_bot, perf_score_bot = compute_performance_score(weights, game_duration, bot_player["kills"], bot_player["deaths"], bot_player[
                                                              "assists"], bot_player["cs"], bot_player["gold"], bot_player["damage_dealt"], bot_player["vision_score"])

            # Calculer la différence de PerformanceScore centrée en 50
            diff = perf_score_top - perf_score_bot
            win_point_top = 60 if top_player["is_winner"] else 40
            win_point_bot = 60 if bot_player["is_winner"] else 40
            alpha = 1 / (1 + matrix_P.trace())
            print(
                f"Position: {position}, Alpha: {alpha}, Matrix P Trace: {matrix_P.trace()}")
            y_top = (50 + (diff / 2)) * alpha + (1 - alpha) * win_point_top
            y_bot = (50 - (diff / 2)) * alpha + (1 - alpha) * win_point_bot

            # Mettre à jour les poids pour chaque joueur de la lane
            rls = RecursiveLeastSquares(n_features=5)
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

            skill_top = get_player_skill(db_path, top_player["player_id"])
            mu_top, sigma_top = None, None
            if skill_top is None:
                mu_top, sigma_top = 50.0, 50.0 / 3
                insert_player_skill(
                    db_path, top_player["player_id"], mu_top, sigma_top)
            else:
                mu_top, sigma_top = skill_top
            ksf_top = KalmanSkillFilter(mu0=mu_top, sigma0=sigma_top)
            ksf_top.predict()
            ksf_top.update(y_top)
            new_mu_top, new_sigma_top = ksf_top.get_state()
            update_player_skill(
                db_path, top_player["player_id"], new_mu_top, new_sigma_top)

            skill_bot = get_player_skill(db_path, bot_player["player_id"])
            mu_bot, sigma_bot = None, None
            if skill_bot is None:
                mu_bot, sigma_bot = 50.0, 50.0 / 3
                insert_player_skill(
                    db_path, bot_player["player_id"], mu_bot, sigma_bot)
            else:
                mu_bot, sigma_bot = skill_bot
            ksf_bot = KalmanSkillFilter(mu0=mu_bot, sigma0=sigma_bot)
            ksf_bot.predict()
            ksf_bot.update(y_bot)
            new_mu_bot, new_sigma_bot = ksf_bot.get_state()
            update_player_skill(
                db_path, bot_player["player_id"], new_mu_bot, new_sigma_bot)

            print(f"Lane {position} - Top Player Skill: mu={new_mu_top:.2f}, sigma={new_sigma_top:.2f} | Bot Player Skill: mu={new_mu_bot:.2f}, sigma={new_sigma_bot:.2f}")

            skills[top_player["riot_id"]] = (new_mu_top, new_sigma_top, "top")
            skills[bot_player["riot_id"]] = (new_mu_bot, new_sigma_bot, "bot")

    return skills, "top" if winner == "top" else "bot"


def top_players(db_path: str, offset: int = 0, limit: int = 10):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    query = """
    SELECT riot_id, skill_mu, skill_sigma
    FROM players
    JOIN player_skill ON players.player_id = player_skill.player_id
    ORDER BY skill_mu DESC
    LIMIT ? OFFSET ?;
    """
    cursor.execute(query, (limit, offset))
    results = cursor.fetchall()

    top_players_list = []
    for row in results:
        riot_id, mu, sigma = row
        top_players_list.append({
            "riot_id": riot_id,
            "mu": mu,
            "sigma": sigma
        })

    cursor.close()
    conn.close()

    return top_players_list


def get_all_weights(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    query = """
    SELECT role, kda_weight, cs_weight, gold_weight, damage_weight, vision_weight, matrix_P
    FROM performance_weights;
    """
    cursor.execute(query)
    results = cursor.fetchall()

    weights_dict = {}
    for row in results:
        position, weight_kda, weight_cs, weight_gold, weight_damage_dealt, weight_vision_score, matrix_P_blob = row
        matrix_P = np.frombuffer(
            matrix_P_blob, dtype=np.float64).reshape((5, 5))
        weights_dict[position] = {
            "kda": weight_kda,
            "cs": weight_cs,
            "gold": weight_gold,
            "damage_dealt": weight_damage_dealt,
            "vision_score": weight_vision_score,
            "P_trace": float(np.trace(matrix_P))
        }

    cursor.close()
    conn.close()

    return weights_dict
