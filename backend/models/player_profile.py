import sqlite3

import pandas as pd

# --- AJOUT ---
from models.database import get_active_features


def get_player_profile_data(db_path: str, riot_id: str):
    """
    Récupère et agrège les statistiques pour un seul joueur.
    """
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # 1. Trouver le joueur et son MMR
    cursor.execute(
        """
        SELECT p.player_id, ps.skill_mu, ps.skill_sigma
        FROM players p
        LEFT JOIN player_skill ps ON p.player_id = ps.player_id
        WHERE p.riot_id = ?
        """,
        (riot_id,)
    )
    player_data = cursor.fetchone()

    if not player_data:
        conn.close()
        return None  # Joueur non trouvé

    player_id, mu, sigma = player_data

    if mu is None:
        mu = 50.0
        sigma = 50.0 / 3

    # 2. Récupérer toutes les stats de match pour ce joueur
    query = """
    SELECT pms.*, m.game_duration
    FROM player_match_stats pms
    JOIN matches m ON pms.match_id = m.match_id
    WHERE pms.player_id = ?
    """
    df = pd.read_sql_query(query, conn, params=(player_id,))
    conn.close()

    # --- MODIFIÉ : Section de calcul des statistiques ---

    if df.empty:
        # Le joueur est dans la base mais n'a pas de matchs
        return {
            "riot_id": riot_id,
            "mu": mu,
            "sigma": sigma,
            "total_games": 0,
            "winrate": 0,
            "main_role": "Inconnu",
            "favorite_champion": "Inconnu",
            "role_specific_avg_stats": {}  # Stats vides
        }

    # 3. Calculer toutes les métriques possibles (pour être sûr)
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

    # 4. Agréger les infos du profil
    total_games = len(df)
    winrate = (df['winner'].sum() / total_games) * 100
    main_role = df['position'].mode(
    )[0] if not df['position'].empty else "Inconnu"
    favorite_champion = df['champion'].mode(
    )[0] if not df['champion'].empty else "Inconnu"

    # 5. Récupérer les features RLS pour le rôle principal et calculer les moyennes
    active_features_config = get_active_features()
    # Utilise une liste de base si le rôle est "Inconnu"
    features_for_role = active_features_config.get(
        main_role, ["kda", "gold_per_min"])

    role_specific_avg_stats = {}
    for feature in features_for_role:
        if feature in df.columns:
            role_specific_avg_stats[feature] = df[feature].mean()
        else:
            # Sécurité au cas où une feature active n'existe pas
            role_specific_avg_stats[feature] = 0.0

    # 6. Retourner le profil complet
    return {
        "riot_id": riot_id,
        "mu": mu,
        "sigma": sigma,
        "total_games": total_games,
        "winrate": winrate,
        "main_role": main_role,
        "favorite_champion": favorite_champion,
        "role_specific_avg_stats": role_specific_avg_stats  # Renvoie les stats spécifiques
    }
