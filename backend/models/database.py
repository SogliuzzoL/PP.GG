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
from utils.feature_selector import recommend_features
from utils.performance import (
    KalmanSkillFilter,
    RecursiveLeastSquares,
    calculate_z_scores,
)


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
        return pd.DataFrame()  # Retourne un DF vide, les appelants doivent vérifier

    # --- Renommage et conversion ---
    if 'position' in df.columns:
        df.rename(columns={'position': 'role'}, inplace=True)
    else:
        print("Erreur critique : La colonne 'position' est manquante dans la BDD.")
        return pd.DataFrame()

    if 'winner' in df.columns:
        df['win'] = df['winner'].astype(int)
        df = df.drop(columns=['winner'])
    else:
        print("Erreur critique : La colonne 'winner' est manquante dans la BDD.")
        return pd.DataFrame()

    # --- Calcul des métriques ---
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

    # Gérer les None possibles avant les calculs
    df['time_ccing_others'] = df['time_ccing_others'].fillna(0)
    df['total_heal_on_teammates'] = df['total_heal_on_teammates'].fillna(0)
    df['total_damage_shielded_on_teammates'] = df['total_damage_shielded_on_teammates'].fillna(
        0)
    df['total_damage_self_mitigated'] = df['total_damage_self_mitigated'].fillna(
        0)
    df['total_heal'] = df['total_heal'].fillna(0)

    df['cc_score_per_min'] = df['time_ccing_others'] / df['game_duration']
    df['healing_on_teammates_per_min'] = df['total_heal_on_teammates'] / \
        df['game_duration']
    df['shields_on_teammates_per_min'] = df['total_damage_shielded_on_teammates'] / \
        df['game_duration']
    df['effective_tanking_per_min'] = (df['total_damage_self_mitigated'] + (
        df['total_heal'] - df['total_heal_on_teammates'])) / df['game_duration']

    final_columns = [
        "match_id", "win", "role", "kda", "kill_participation", "cs_per_min", "gold_per_min",
        "damage_dealt_per_min", "team_damage_percentage", "vision_score_per_min",
        "vision_control_per_min", "cc_score_per_min", "healing_on_teammates_per_min",
        "shields_on_teammates_per_min", "effective_tanking_per_min"
    ]

    existing_columns = [col for col in final_columns if col in df.columns]
    # Remplacer les NaN/None restants par 0
    return df[existing_columns].fillna(0)


def retrain_rls_model(role: str, new_features: list, historical_df: pd.DataFrame, limit_games=20):
    """
    Réentraîne un modèle RLS en utilisant les X dernières parties,
    en appliquant le Z-Score PAR MATCH pour la stabilité.
    """
    print(
        f"Réentraînement du modèle pour {role} avec les features : {new_features}")

    n_features = len(new_features)
    rls = RecursiveLeastSquares(n_features=n_features)

    # 1. Obtenir les X dernières parties pour ce rôle
    role_df = historical_df[historical_df['role'] == role]
    if role_df.empty:
        print(
            f"Pas de données historiques pour {role}. Initialisation par défaut.")
        weights = {feature: 0.01 for feature in new_features}
        matrix_P = np.eye(n_features) * 1000
        return weights, matrix_P

    recent_match_ids = role_df['match_id'].unique()[-limit_games:]

    # 2. Obtenir TOUS les joueurs de ces parties (pour le contexte Z-Score)
    train_df = historical_df[historical_df['match_id'].isin(
        recent_match_ids)].copy()

    if train_df.empty:
        print(
            f"Aucune donnée d'entraînement trouvée pour {role}. Initialisation par défaut.")
        weights = {feature: 0.01 for feature in new_features}
        matrix_P = np.eye(n_features) * 1000
        return weights, matrix_P

    # 3. Appliquer le Z-Score PAR MATCH (la clé)
    scaled_train_df = train_df.copy()

    for feature in new_features:
        if feature not in scaled_train_df.columns:
            print(
                f"Attention : feature {feature} non trouvée lors du retrain.")
            # Mettre une valeur par défaut (Z-Score de 0)
            scaled_train_df[feature] = 0.0
            continue

        # Utilise groupby.transform pour scaler chaque joueur par rapport à son propre match
        mean = scaled_train_df.groupby('match_id')[feature].transform('mean')
        std = scaled_train_df.groupby('match_id')[feature].transform('std')

        # Remplacer std=0 (si tous les joueurs ont la même stat) par 1 pour éviter la division par 0
        std = std.replace(0, 1)

        # <<< MODIFICATION : On garde le Z-Score brut (centré à 0)
        z_scores = (scaled_train_df[feature] - mean) / std
        scaled_train_df[feature] = z_scores

    # 4. Entraîner le RLS uniquement sur les joueurs du bon rôle
    role_players_to_train = scaled_train_df[scaled_train_df['role'] == role]

    for _, row in role_players_to_train.iterrows():
        try:
            x = np.array([row[f] for f in new_features])
        except KeyError:
            print(f"Erreur de clé lors de la création du vecteur x pour le retrain.")
            continue  # Ignorer cette ligne

        # <<< MODIFICATION : Cible changée à +1.0 / -1.0
        y = 1.0 if row['win'] == 1 else -1.0
        rls.update(x, y)

    # 5. Retourner les poids appris
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
                if role == "UNKNOWN":
                    role = "UTILITY"  # Fallback

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

                auto_heal = (total_heal or 0) - (healing_on_teammates or 0)
                player_metrics = {
                    "kda": (kills + assists) / max(1, deaths),
                    "kill_participation": (kills + assists) / max(1, team_kills[team["teamId"]]) * 100,
                    "cs_per_min": cs / game_duration_min,
                    "gold_per_min": gold / game_duration_min,
                    "damage_dealt_per_min": damage_dealt / game_duration_min,
                    "team_damage_percentage": (damage_dealt / max(1, team_damage[team["teamId"]])) * 100,
                    "vision_score_per_min": vision_score / game_duration_min,
                    "vision_control_per_min": (stats.get("WARD_KILLED", 0) * 1.5 + stats.get("VISION_WARDS_BOUGHT_IN_GAME", 0) * 1.0) / game_duration_min,
                    "cc_score_per_min": (cc_score or 0) / game_duration_min,
                    "healing_on_teammates_per_min": (healing_on_teammates or 0) / game_duration_min,
                    "shields_on_teammates_per_min": (shield_on_teammates or 0) / game_duration_min,
                    "effective_tanking_per_min": ((damage_mitigated or 0) + auto_heal) / game_duration_min,
                }

                all_players_data.append({
                    "player_id": player_id, "riot_id": riot_id, "position": role,
                    "team_side": team_side, "is_winner": team_side == winner,
                    "metrics": player_metrics
                })

        cursor.close()

        # --- 1. Calcul Z-Score (pour CE match) ---
        all_feature_names = [
            "kda", "kill_participation", "cs_per_min", "gold_per_min",
            "damage_dealt_per_min", "team_damage_percentage", "vision_score_per_min",
            "vision_control_per_min", "cc_score_per_min", "healing_on_teammates_per_min",
            "shields_on_teammates_per_min", "effective_tanking_per_min"
        ]

        z_scores_by_feature = {}
        for feature_name in all_feature_names:
            if feature_name not in all_players_data[0]["metrics"]:
                print(
                    f"Avertissement : {feature_name} n'est pas dans player_metrics. Ignoré.")
                continue
            stats_list = [p["metrics"].get(feature_name, 0)
                          for p in all_players_data]
            z_scores_by_feature[feature_name] = calculate_z_scores(stats_list)

        # <<< MODIFICATION : 'scaled_metrics_by_feature' (50-centré) est supprimé.

        # --- 2. Initialisation des Modèles RLS (avec Retraining) ---

        historical_df = get_all_historical_data(conn)
        new_recommended_features = recommend_features(historical_df)

        rls_models = {}
        all_roles = set(p["position"] for p in all_players_data)

        for role in all_roles:
            ideal_features = new_recommended_features.get(
                role, active_features_config.get(role))
            if ideal_features is None:
                ideal_features = ["kda", "gold_per_min"]

            stored_features, stored_weights, stored_matrix_P = get_weights_for_role(
                conn, role)

            n_features = len(ideal_features)

            if stored_features != ideal_features or stored_weights is None:
                print(
                    f"Changement de features ou 1er démarrage pour {role}. Ré-entraînement...")
                weights, matrix_P = retrain_rls_model(
                    role, ideal_features, historical_df, limit_games=20)
            else:
                weights = stored_weights
                matrix_P = stored_matrix_P

            rls = RecursiveLeastSquares(n_features=n_features)
            rls.weights = np.array([weights.get(f, 0.01)
                                   for f in ideal_features])
            rls.P = matrix_P
            rls_models[role] = (rls, ideal_features)

        # --- 3. Calcul du Score de Performance Brut ---
        player_perf_scores_raw = []
        for i, p_data in enumerate(all_players_data):
            role = p_data["position"]
            rls, ideal_features = rls_models[role]

            try:
                # <<< MODIFICATION : Utilise les Z-SCORES BRUTS (centrés à 0)
                feature_vector = np.array(
                    [z_scores_by_feature[feature][i] for feature in ideal_features])
            except KeyError as e:
                print(
                    f"Erreur de feature manquante pour {role}: {e}. Vecteur nul.")
                feature_vector = np.zeros(len(ideal_features))

            p_data["feature_vector"] = feature_vector

            # Le score sera maintenant centré autour de 0 (ex: -0.5 à +0.5)
            perf_score_raw = np.dot(rls.weights, feature_vector)
            p_data["perf_score_raw"] = perf_score_raw
            player_perf_scores_raw.append(perf_score_raw)

        # --- 4. Normalisation Min-Max du Score (20-80) ---
        min_score = min(player_perf_scores_raw)
        max_score = max(player_perf_scores_raw)

        for p_data in all_players_data:
            perf_raw = p_data["perf_score_raw"]
            if (max_score - min_score) == 0:
                p_data["normalized_score"] = 50.0
            else:
                p_data["normalized_score"] = 20 + 60 * \
                    (perf_raw - min_score) / (max_score - min_score)

        # Calcul du skill moyen de la partie
        avg_skill = 0.0
        for p_data in all_players_data:
            skill = get_player_skill(conn, p_data["player_id"])
            mu = 50.0 if skill is None else skill[0]
            avg_skill += mu
        avg_skill /= len(all_players_data)
        print(f"Skill moyen de la partie : {avg_skill:.2f}")

        # --- 5. Mise à jour Kalman (Skill) et préparation RLS ---
        skills = {}
        updated_roles_data = defaultdict(list)

        for p_data in all_players_data:
            role = p_data["position"]

            # <<< MODIFICATION : Cible RLS changée à +1.0 / -1.0
            y_rls = 1.0 if p_data["is_winner"] else -1.0

            skill = get_player_skill(conn, p_data["player_id"])
            # Garde le 50-centré pour le MU
            mu, sigma = (50.0, 50.0 / 3) if skill is None else skill
            if skill is None:
                insert_player_skill(conn, p_data["player_id"], mu, sigma)

            # Calcul de la difficulté relative
            y_difficulty = avg_skill - mu

            # Calcul de y_kalman
            K = 0.5
            y_kalman = p_data["normalized_score"] + K * y_difficulty

            ksf = KalmanSkillFilter(mu0=mu, sigma0=sigma)
            ksf.predict()
            ksf.update(y_kalman)  # Update avec le score [20-80]

            new_mu, new_sigma = ksf.get_state()
            update_player_skill(conn, p_data["player_id"], new_mu, new_sigma)

            updated_roles_data[role].append({
                "x": p_data["feature_vector"],  # Z-Score brut
                "y": y_rls                     # Cible +1.0 / -1.0
            })

            skills[p_data["riot_id"]] = {
                "mu": new_mu, "sigma": new_sigma, "team": p_data["team_side"],
                "normalized_score": p_data["normalized_score"],
                "difficulty": y_difficulty,
                "y": y_kalman,
                "position": role
            }

        # --- 6. Mise à jour des modèles RLS (Poids) ---
        for role, updates in updated_roles_data.items():
            rls, current_features = rls_models[role]
            for update_data in updates:
                rls.update(update_data["x"], update_data["y"])

            new_weights = {name: float(val) for name, val in zip(
                current_features, rls.weights)}
            save_weights_for_role(
                conn, role, current_features, new_weights, rls.P)

        conn.commit()
        return skills, winner, avg_skill

    except Exception as e:
        conn.rollback()
        print(f"Erreur lors de l'ajout du match : {e}")
        raise e
    finally:
        conn.close()


def top_players(db_path: str, offset: int = 0, limit: int = 10):
    conn = sqlite3.connect(db_path)
    try:
        cursor = conn.cursor()
        # On calcule (mu - 3*sigma) sous le nom 'rating' pour le tri et l'affichage
        query = """
        SELECT riot_id, skill_mu, skill_sigma, (skill_mu - 3 * skill_sigma) as rating
        FROM players
        JOIN player_skill ON players.player_id = player_skill.player_id
        ORDER BY rating DESC
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
        riot_id, mu, sigma, rating = row
        top_players_list.append({
            "riot_id": riot_id,
            # On peut garder mu et sigma pour le détail, ou les cacher si on veut simplifier
            "mu": round(mu, 2),
            "sigma": round(sigma, 2),
            # Ce 'rating' est ce que le joueur doit regarder pour son classement
            "rating": round(rating, 2) 
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
