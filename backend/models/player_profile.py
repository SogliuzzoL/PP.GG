import sqlite3

import pandas as pd
from models.database import get_active_features
from models.performance_weights import get_weights_for_role


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

    if df.empty:
        conn.close()
        return {
            "riot_id": riot_id,
            "mu": mu,
            "sigma": sigma,
            "total_games": 0,
            "winrate": 0,
            "main_role": "Inconnu",
            "secondary_role": "Aucun",
            "top_champions": [],
            "role_specific_avg_stats": {}
        }

    # 3. Calculer toutes les métriques pour TOUS les matchs (nécessaire pour le filtrage ultérieur)
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

    # 4. Agréger les infos GLOBALES du profil (Winrate global, top champions globaux, détermination des rôles)
    total_games = len(df)
    winrate = (df['winner'].sum() / total_games) * 100

    role_counts = df['position'].value_counts()
    main_role = role_counts.index[0] if not role_counts.empty else "Inconnu"
    secondary_role = role_counts.index[1] if len(role_counts) > 1 else "Aucun"

    champion_counts = df['champion'].value_counts()
    print("Champion counts for", riot_id, ":", champion_counts.to_dict())
    top_champions = [
        {"name": champ, "count": int(count), "winrate": float(
            df[df['champion'] == champ]['winner'].mean() * 100)}
        for champ, count in champion_counts.head(5).items()
    ]

    # 5. Récupérer les features RLS
    # On cherche les poids qui correspondent au MAIN ROLE
    # stored_features, _, _ = get_weights_for_role(conn, main_role)
    conn.close()  # On peut fermer ici car on a fini avec SQL

    # print("Features utilisées pour le rôle", main_role, ":", stored_features)

    # if stored_features:
    #     features_for_role = stored_features
    # else:
    #     active_features_config = get_active_features()
    #     features_for_role = active_features_config.get(
    #         main_role, ["kda", "gold_per_min"])

    features_for_role = ["kda", "kill_participation", "cs_per_min", "gold_per_min",
                         "damage_dealt_per_min", "vision_score_per_min",
                         "cc_score_per_min", "healing_on_teammates_per_min",
                         "shields_on_teammates_per_min", "effective_tanking_per_min"]

    # --- CORRECTION PRINCIPALE ---
    # On crée un DataFrame filtré qui ne contient QUE les matchs du main_role
    # pour calculer les moyennes spécifiques à ce rôle.
    df_main_role = df[df['position'] == main_role]

    role_specific_avg_stats = {}

    if not df_main_role.empty:
        for feature in features_for_role:
            if feature in df_main_role.columns:
                # On utilise df_main_role ici, pas df
                val = df_main_role[feature].mean()
                # Gestion des NaN si jamais (division par zero etc)
                role_specific_avg_stats[feature] = 0.0 if pd.isna(val) else val
            else:
                role_specific_avg_stats[feature] = 0.0
    else:
        # Si jamais le joueur a un main_role détecté mais 0 matchs dedans (cas théorique improbable via value_counts mais possible via bugs)
        for feature in features_for_role:
            role_specific_avg_stats[feature] = 0.0

    # 6. Retourner le profil complet
    return {
        "riot_id": riot_id,
        "mu": mu,
        "sigma": sigma,
        "total_games": total_games,
        "winrate": winrate,
        "main_role": main_role,
        "secondary_role": secondary_role,
        "top_champions": top_champions,
        "role_specific_avg_stats": role_specific_avg_stats
    }
