import json
import os
from collections import defaultdict

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns


def extract_player_stats_from_json(file_path):
    """
    Extrait et calcule les statistiques de tous les joueurs d'un unique fichier JSON de fin de partie.
    """
    with open(file_path, 'r', encoding='utf-8') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError:
            print(
                f"Avertissement : Erreur de décodage JSON pour le fichier : {file_path}")
            return []

    player_stats_list = []
    game_duration_min = data.get("gameLength", 1) / 60.0

    team_kills = defaultdict(int)
    for team in data.get("teams", []):
        team_id = team.get("teamId")
        for player in team.get("players", []):
            team_kills[team_id] += player.get("stats",
                                              {}).get("CHAMPIONS_KILLED", 0)

    for team in data.get("teams", []):
        for player in team.get("players", []):
            stats = player.get("stats", {})
            if not stats:
                continue

            kills = stats.get("CHAMPIONS_KILLED", 0)
            deaths = stats.get("NUM_DEATHS", 1)
            assists = stats.get("ASSISTS", 0)
            kda = (kills + assists) / max(1, deaths)

            team_id = player.get("teamId")
            total_team_kills = team_kills.get(team_id, 1)
            kill_participation = (kills + assists) / \
                max(1, total_team_kills) * 100

            wards_killed = stats.get("WARD_KILLED", 0)
            control_wards_bought = stats.get("VISION_WARDS_BOUGHT_IN_GAME", 0)
            vision_control_score = (wards_killed * 1.5) + \
                (control_wards_bought * 1.0)

            self_mitigated = stats.get("TOTAL_DAMAGE_SELF_MITIGATED", 0)
            auto_heal = stats.get("TOTAL_HEAL", 0) - \
                stats.get("TOTAL_HEAL_ON_TEAMMATES", 0)
            effective_tanking = self_mitigated + auto_heal

            role = player.get("detectedTeamPosition", "UNKNOWN").upper()
            if role == "MID":
                role = "MIDDLE"
            if role in ["SUPPORT", "SUPP"]:
                role = "UTILITY"

            player_data = {
                "win": 1 if team.get("isWinningTeam") else 0,
                "role": role,
                "kda": kda,
                "kill_participation": kill_participation,
                "cs_per_min": (stats.get("MINIONS_KILLED", 0) + stats.get("NEUTRAL_MINIONS_KILLED", 0)) / game_duration_min,
                "gold_per_min": stats.get("GOLD_EARNED", 0) / game_duration_min,
                "damage_dealt_per_min": stats.get("TOTAL_DAMAGE_DEALT_TO_CHAMPIONS", 0) / game_duration_min,
                "vision_score_per_min": stats.get("VISION_SCORE", 0) / game_duration_min,
                "vision_control_per_min": vision_control_score / game_duration_min,
                "cc_score_per_min": stats.get("TIME_CCING_OTHERS", 0) / game_duration_min,
                "healing_on_teammates_per_min": stats.get("TOTAL_HEAL_ON_TEAMMATES", 0) / game_duration_min,
                "shields_on_teammates_per_min": stats.get("TOTAL_DAMAGE_SHIELDED_ON_TEAMMATES", 0) / game_duration_min,
                "effective_tanking_per_min": effective_tanking / game_duration_min,
            }
            player_stats_list.append(player_data)

    return player_stats_list


def select_features_intelligently(correlation_matrix, win_threshold, internal_threshold):
    """
    Algorithme de sélection de features basé sur la corrélation.
    """
    correlations_with_win = correlation_matrix['win'].drop('win')
    candidates = correlations_with_win[correlations_with_win >= win_threshold]
    sorted_candidates = candidates.sort_values(ascending=False)

    if sorted_candidates.empty:
        return []

    final_features = []
    final_features.append(sorted_candidates.index[0])

    for new_feature in sorted_candidates.index[1:]:
        is_redundant = False
        for selected_feature in final_features:
            internal_correlation = correlation_matrix.loc[new_feature,
                                                          selected_feature]
            if internal_correlation > internal_threshold:
                is_redundant = True
                break

        if not is_redundant:
            final_features.append(new_feature)

    return final_features


def analyze_and_recommend_features(folder_path, win_corr_threshold=0.40, internal_corr_threshold=0.75):
    """
    Fonction principale qui lit les données, enregistre les matrices de corrélation 
    et recommande les features pour chaque rôle.
    """
    all_game_stats = []

    if not os.path.isdir(folder_path):
        print(f"Erreur : Le dossier '{folder_path}' n'existe pas.")
        return

    for filename in os.listdir(folder_path):
        if filename.endswith(".json"):
            file_path = os.path.join(folder_path, filename)
            game_stats = extract_player_stats_from_json(file_path)
            all_game_stats.extend(game_stats)

    if not all_game_stats:
        print("Aucune donnée de joueur n'a été trouvée dans les fichiers JSON.")
        return

    df = pd.DataFrame(all_game_stats)
    roles = sorted([role for role in df['role'].unique() if role != "UNKNOWN"])

    recommended_config = {}

    for role in roles:
        print(f"\n--- Analyse pour le Rôle : {role} ---")

        role_df = df[df['role'] == role]
        if len(role_df) < 2:
            print(f"Pas assez de données pour le rôle {role}.")
            continue

        numeric_role_df = role_df.select_dtypes(include=['number'])
        correlation_matrix = numeric_role_df.corr()

        # 1. Enregistrement de la matrice de corrélation en PNG
        plt.figure(figsize=(14, 12))
        sns.heatmap(correlation_matrix, annot=True,
                    cmap='coolwarm', fmt=".2f", linewidths=.5)
        plt.title(f'Matrice de Corrélation - Rôle : {role}')
        output_filename = f"correlation_matrix_{role}.png"
        plt.savefig(output_filename, bbox_inches='tight')
        plt.close()
        print(f"Matrice de corrélation enregistrée dans : {output_filename}")

        # 2. Sélection des features via l'algorithme
        selected_features = select_features_intelligently(
            correlation_matrix,
            win_corr_threshold,
            internal_corr_threshold
        )
        recommended_config[role] = selected_features

    # 3. Affichage du résultat final
    print("\n\n--- Recommandations Finales de Features par Rôle ---")
    print(f"(Basé sur {len(df) // 10} parties analysées)\n")
    print("activate_weights = {")
    for role, features in recommended_config.items():
        print(f'    "{role}": {features},')
    print("}")


if __name__ == "__main__":
    # --- VOS PARAMÈTRES ---
    # 1. Chemin vers le dossier contenant vos fichiers JSON
    GAMES_FOLDER_PATH = "sent_uploads"

    # 2. Seuil de corrélation minimale avec la victoire pour considérer une feature
    WIN_CORRELATION_THRESHOLD = 0.40

    # 3. Seuil de corrélation pour considérer deux features comme redondantes
    INTERNAL_CORRELATION_THRESHOLD = 0.75
    # --- FIN DES PARAMÈTRES ---

    analyze_and_recommend_features(
        GAMES_FOLDER_PATH,
        WIN_CORRELATION_THRESHOLD,
        INTERNAL_CORRELATION_THRESHOLD
    )
