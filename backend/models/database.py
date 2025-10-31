import json
import sqlite3
from collections import defaultdict

import numpy as np
import pandas as pd
from flask import jsonify
from models.match import insert_match
from models.performance_weights import get_weights_for_role, save_weights_for_role
from models.player import create_player, get_player, update_player
from models.player_match_stats import insert_player_match_stats
from models.player_skill import (
    get_player_skill,
    insert_player_skill,
    update_player_skill,
)

# Importe depuis vos fichiers utils séparés
from utils.feature_selector import recommend_features
from utils.performance import KalmanSkillFilter, RecursiveLeastSquares


def initialize_db(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    tables = [
        "matches", "player_match_stats", "player_riot_id_history", "players",
        "api_tokens", "player_skill", "performance_weights",
    ]

    for table in tables:
        try:
            with open(f"backend/models/tables/{table}.sql", "r") as f:
                sql_script = f.read()
            cursor.execute(sql_script)
        except FileNotFoundError:
            print(
                f"Avertissement : Le fichier backend/models/tables/{table}.sql n'a pas été trouvé.")
        except Exception as e:
            print(f"Erreur lors de l'initialisation de la table {table}: {e}")

    cursor.close()
    conn.commit()
    conn.close()


def get_active_features():
    """Charge la configuration des features depuis le fichier JSON."""
    try:
        with open("backend/active_features.json", 'r') as f:
            return json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        print("Avertissement : backend/active_features.json non trouvé. Utilisation d'un fallback.")
        return {
            "TOP": ["kda", "gold_per_min"], "JUNGLE": ["kda", "gold_per_min"],
            "MIDDLE": ["kda", "gold_per_min"], "BOTTOM": ["kda", "gold_per_min"],
            "UTILITY": ["kda", "vision_score_per_min"],
        }


def get_all_historical_data(conn: sqlite3.Connection):
    """
    Récupère toutes les données de performance historiques pour l'analyse
    et calcule les métriques normalisées.
    """
    query = """
    SELECT pms.*, m.game_duration
    FROM player_match_stats pms
    JOIN matches m ON pms.match_id = m.match_id
    """
    try:
        df = pd.read_sql_query(query, conn)
    except pd.io.sql.DatabaseError:
        print("Avertissement : La table 'player_match_stats' est vide.")
        df = pd.DataFrame()

    if df.empty:
        return pd.DataFrame(columns=[
            "win", "role", "kda", "kill_participation", "cs_per_min", "gold_per_min",
            "damage_dealt_per_min", "team_damage_percentage", "vision_score_per_min",
            "vision_control_per_min", "cc_score_per_min", "healing_on_teammates_per_min",
            "shields_on_teammates_per_min", "effective_tanking_per_min"
        ])

    # --- CORRECTION KeyError 'role' ---
    if 'position' in df.columns:
        df.rename(columns={'position': 'role'}, inplace=True)
    else:
        print("Erreur critique : La colonne 'position' est manquante dans la BDD.")
        return pd.DataFrame()

    # --- CORRECTION KeyError 'win' ---
    if 'winner' in df.columns:
        df['win'] = df['winner'].astype(int)
        # Supprime la colonne 'winner' originale
        df = df.drop(columns=['winner'])
    else:
        print("Erreur critique : La colonne 'winner' est manquante dans la BDD.")
        return pd.DataFrame()
    # --- FIN DES CORRECTIONS ---

    df['game_duration'] = df['game_duration'].replace(0, 1)
    df['kda'] = (df['kills'] + df['assists']) / df['deaths'].replace(0, 1)
    df['kill_participation'] = (
        df['kills'] + df['assists']) / df['total_team_kills'].replace(0, 1) * 100
    df['cs_per_min'] = df['cs'] / df['game_duration']
    df['gold_per_min'] = df['gold_earned'] / df['game_duration']
    df['damage_dealt_per_min'] = df['total_damage_dealt_to_champions'] / \
        df['game_duration']
    df['team_damage_percentage'] = (
        df['total_damage_dealt_to_champions'] / df['total_team_damage'].replace(0, 1)) * 100
    df['vision_score_per_min'] = df['vision_score'] / df['game_duration']
    df['vision_control_per_min'] = (
        df['wards_killed'] * 1.5 + df['vision_wards_bought_in_game'] * 1.0) / df['game_duration']
    df['cc_score_per_min'] = df['time_ccing_others'] / df['game_duration']
    df['healing_on_teammates_per_min'] = df['total_heal_on_teammates'] / \
        df['game_duration']
    df['shields_on_teammates_per_min'] = df['total_damage_shielded_on_teammates'] / \
        df['game_duration']
    df['effective_tanking_per_min'] = (df['total_damage_self_mitigated'] + (
        df['total_heal'] - df['total_heal_on_teammates'])) / df['game_duration']

    final_columns = [
        "win", "role", "kda", "kill_participation", "cs_per_min", "gold_per_min",
        "damage_dealt_per_min", "team_damage_percentage", "vision_score_per_min",
        "vision_control_per_min", "cc_score_per_min", "healing_on_teammates_per_min",
        "shields_on_teammates_per_min", "effective_tanking_per_min"
    ]

    # S'assure que seules les colonnes qui existent réellement dans le DataFrame sont sélectionnées
    # (au cas où une colonne n'aurait pas pu être calculée)
    existing_columns = [col for col in final_columns if col in df.columns]

    return df[existing_columns]


def retrain_rls_model(role, new_features, historical_df, limit=20):
    """
    Crée et réentraîne un nouveau modèle RLS sur les X dernières parties
    pour ce rôle spécifique.
    """
    print(
        f"Réentraînement du modèle pour {role} avec les features : {new_features}")

    role_history = historical_df[historical_df['role'] == role].tail(limit)
    n_features = len(new_features)

    if role_history.empty or len(role_history) < 2:
        print(
            f"Pas assez de données pour le réentraînement de {role}. Initialisation par défaut.")
        weights = {feature: 0.1 for feature in new_features}
        matrix_P = np.eye(n_features) * 1000
        return weights, matrix_P

    rls = RecursiveLeastSquares(n_features=n_features)
    for _, row in role_history.iterrows():
        try:
            x_data = [row[feature] for feature in new_features]
            x = np.array(x_data)
        except KeyError as e:
            print(
                f"Erreur: Feature '{e}' non trouvée dans les données historiques. Réinitialisation.")
            weights = {feature: 0.1 for feature in new_features}
            matrix_P = np.eye(n_features) * 1000
            return weights, matrix_P

        y = 60.0 if row['win'] == 1 else 40.0
        rls.update(x, y)

    new_weights = {name: float(val)
                   for name, val in zip(new_features, rls.weights)}
    return new_weights, rls.P


def add_match(db_path: str, data: dict):

    conn = sqlite3.connect(db_path)

    try:
        active_features_config = get_active_features()

        game_duration_min = data.get("gameLength", 1) / 60.0
        winner = "bot" if (data["teams"][0]["isBottomTeam"] and data["teams"][0]["isWinningTeam"]) or \
            (not data["teams"][0]["isBottomTeam"] and not data["teams"][0]["isWinningTeam"]) else "top"

        match_id = insert_match(conn, game_duration_min, winner)

        team_kills = defaultdict(int)
        team_damage = defaultdict(float)

        for team in data["teams"]:
            team_id = team["teamId"]
            for player in team["players"]:
                stats = player.get("stats", {})
                team_kills[team_id] += stats.get("CHAMPIONS_KILLED", 0)
                team_damage[team_id] += stats.get(
                    "TOTAL_DAMAGE_DEALT_TO_CHAMPIONS", 0)

        all_players_data = []
        cursor = conn.cursor()

        for team in data["teams"]:
            team_side = "bot" if team["isBottomTeam"] else "top"
            for player in team["players"]:
                player_id = get_player(conn, player["puuid"])
                riot_id = f"{player['riotIdGameName']}#{player['riotIdTagLine']}"
                if not player_id:
                    player_id = create_player(conn, player["puuid"], riot_id)
                else:
                    update_player(conn, player_id, riot_id)

                stats = player.get("stats", {})
                role = player.get("detectedTeamPosition", "UNKNOWN").upper()
                if role == "MID":
                    role = "MIDDLE"
                if role in ["SUPPORT", "SUPP"]:
                    role = "UTILITY"

                kills = stats.get("CHAMPIONS_KILLED", 0)
                deaths = stats.get("NUM_DEATHS", 0)
                assists = stats.get("ASSISTS", 0)
                cs = stats.get("MINIONS_KILLED", 0) + \
                    stats.get("NEUTRAL_MINIONS_KILLED", 0)
                gold = stats.get("GOLD_EARNED", 0)
                damage_dealt = stats.get("TOTAL_DAMAGE_DEALT_TO_CHAMPIONS", 0)
                vision_score = stats.get("VISION_SCORE", 0)
                cc_score = stats.get("TIME_CCING_OTHERS", 0)
                healing_on_teammates = stats.get("TOTAL_HEAL_ON_TEAMMATES", 0)
                shield_on_teammates = stats.get(
                    "TOTAL_DAMAGE_SHIELDED_ON_TEAMMATES", 0)
                damage_mitigated = stats.get("TOTAL_DAMAGE_SELF_MITIGATED", 0)
                total_heal = stats.get("TOTAL_HEAL", 0)

                insert_player_match_stats(
                    cursor, match_id, player_id, player.get(
                        "championName", "UNKNOWN"), team_side, role,
                    team_side == winner, kills, deaths, assists, team_kills[team["teamId"]],
                    cs, gold, damage_dealt, team_damage[team["teamId"]],
                    vision_score, stats.get("WARD_KILLED", 0), stats.get(
                        "VISION_WARDS_BOUGHT_IN_GAME", 0),
                    cc_score, healing_on_teammates, shield_on_teammates,
                    damage_mitigated, total_heal
                )

                auto_heal = total_heal - healing_on_teammates
                player_metrics = {
                    "kda": (kills + assists) / max(1, deaths),
                    "kill_participation": (kills + assists) / max(1, team_kills[team["teamId"]]) * 100,
                    "cs_per_min": cs / game_duration_min,
                    "gold_per_min": gold / game_duration_min,
                    "damage_dealt_per_min": damage_dealt / game_duration_min,
                    "team_damage_percentage": (damage_dealt / max(1, team_damage[team["teamId"]])) * 100,
                    "vision_score_per_min": vision_score / game_duration_min,
                    "vision_control_per_min": (stats.get("WARD_KILLED", 0) * 1.5 + stats.get("VISION_WARDS_BOUGHT_IN_GAME", 0) * 1.0) / game_duration_min,
                    "cc_score_per_min": cc_score / game_duration_min,
                    "healing_on_teammates_per_min": healing_on_teammates / game_duration_min,
                    "shields_on_teammates_per_min": shield_on_teammates / game_duration_min,
                    "effective_tanking_per_min": (damage_mitigated + auto_heal) / game_duration_min,
                }

                all_players_data.append({
                    "player_id": player_id, "riot_id": riot_id, "position": role,
                    "team_side": team_side, "is_winner": team_side == winner,
                    "metrics": player_metrics
                })

        cursor.close()  # Fin des insertions

        historical_df = get_all_historical_data(conn)
        new_recommended_features = recommend_features(
            historical_df, win_corr_threshold=0.40, internal_corr_threshold=0.75)

        rls_models = {}
        player_perf_scores = []

        for p_data in all_players_data:
            role = p_data["position"]
            if role == "UNKNOWN":
                role = "UTILITY"
                p_data["position"] = "UTILITY"

            stored_features, stored_weights, stored_matrix_P = get_weights_for_role(
                conn, role)

            ideal_features = new_recommended_features.get(
                role, stored_features)
            if ideal_features is None:
                ideal_features = ["kda", "gold_per_min"]
                if role == "UTILITY":
                    ideal_features = ["kda", "vision_score_per_min"]

            if stored_features != ideal_features:
                weights, matrix_P = retrain_rls_model(
                    role, ideal_features, historical_df, limit=20)
            elif stored_features is None:
                n_features = len(ideal_features)
                weights = {feature: 0.1 for feature in ideal_features}
                matrix_P = np.eye(n_features) * 1000
            else:
                weights = stored_weights
                matrix_P = stored_matrix_P

            n_features = len(ideal_features)
            rls = RecursiveLeastSquares(n_features=n_features)
            rls.weights = np.array([weights.get(f, 0.1)
                                   for f in ideal_features])
            rls.P = matrix_P
            rls_models[role] = (rls, ideal_features)

            try:
                feature_vector = np.array(
                    [p_data["metrics"][feature] for feature in ideal_features])
            except KeyError as e:
                print(
                    f"Erreur de feature manquante pour {role}: {e}. Vecteur nul.")
                feature_vector = np.zeros(n_features)

            p_data["feature_vector"] = feature_vector
            p_data["perf_score_raw"] = np.dot(rls.weights, feature_vector)
            player_perf_scores.append(p_data["perf_score_raw"])

        min_score, max_score = min(player_perf_scores), max(player_perf_scores)

        for p_data in all_players_data:
            if max_score == min_score:
                p_data["normalized_score"] = 50.0
            else:
                p_data["normalized_score"] = 20 + 60 * \
                    (p_data["perf_score_raw"] - min_score) / \
                    (max_score - min_score)

        skills = {}
        updated_roles = set()

        for p_data in all_players_data:
            role = p_data["position"]
            rls, current_features = rls_models[role]

            win_point = 60 if p_data["is_winner"] else 40
            alpha = 1 / (1 + rls.P.trace())
            y = p_data["normalized_score"] * alpha + (1 - alpha) * win_point

            rls.update(p_data["feature_vector"], y)

            skill = get_player_skill(conn, p_data["player_id"])
            mu, sigma = (50.0, 50.0 / 3) if skill is None else skill
            if skill is None:
                insert_player_skill(conn, p_data["player_id"], mu, sigma)

            ksf = KalmanSkillFilter(mu0=mu, sigma0=sigma, R=sigma**2)
            ksf.predict()
            ksf.update(y)
            new_mu, new_sigma = ksf.get_state()
            update_player_skill(conn, p_data["player_id"], new_mu, new_sigma)

            if role not in updated_roles:
                new_weights = {name: float(val) for name, val in zip(
                    current_features, rls.weights)}
                save_weights_for_role(
                    conn, role, current_features, new_weights, rls.P)
                updated_roles.add(role)

            skills[p_data["riot_id"]] = {
                "mu": new_mu, "sigma": new_sigma, "team": p_data["team_side"],
                "normalized_score": p_data["normalized_score"], "alpha": alpha, "y": y,
                "position": role
            }

        conn.commit()
        return skills, winner

    except Exception as e:
        conn.rollback()
        print(f"Erreur lors de l'ajout du match : {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()


def top_players(db_path: str, offset: int = 0, limit: int = 10):
    conn = sqlite3.connect(db_path)
    try:
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
        cursor.close()
    except Exception as e:
        print(f"Erreur dans top_players: {e}")
        results = []
    finally:
        conn.close()

    top_players_list = []
    for row in results:
        riot_id, mu, sigma = row
        top_players_list.append({
            "riot_id": riot_id,
            "mu": mu,
            "sigma": sigma
        })
    return top_players_list


def get_all_weights(db_path: str):
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    query = "SELECT role, features_json, weights_json, matrix_P FROM performance_weights;"
    try:
        cursor.execute(query)
        results = cursor.fetchall()
    except sqlite3.OperationalError:
        print("Erreur : La table 'performance_weights' n'existe probablement pas. Initialisation...")
        conn.close()
        initialize_db(db_path)
        return {}
    finally:
        conn.close()

    weights_dict = {}
    for row in results:
        role, features_json, weights_json, matrix_P_blob = row

        features = json.loads(features_json)
        weights = json.loads(weights_json)
        n_features = len(features)

        try:
            matrix_P = np.frombuffer(matrix_P_blob, dtype=np.float64).reshape(
                (n_features, n_features))
            p_trace = float(np.trace(matrix_P))
        except (ValueError, TypeError):
            p_trace = -1.0

        formatted_weights = {}
        for feature in features:
            formatted_weights[feature] = weights.get(feature, 0)
        formatted_weights["P_trace"] = p_trace

        weights_dict[role] = formatted_weights

    return weights_dict
