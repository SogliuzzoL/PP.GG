import sqlite3

import pandas as pd
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

    if df.empty:
        # Le joueur est dans la base mais n'a pas de matchs
        return {
            "riot_id": riot_id,
            "mu": mu,
            "sigma": sigma,
            "total_games": 0,
            "winrate": 0,
            "main_role": "Inconnu",
            "secondary_role": "Aucun",  # AJOUT
            "top_champions": [],        # AJOUT
            "role_specific_avg_stats": {}
        }

    # 3. Calculer toutes les métriques (inchangé)
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

    # 4. Agréger les infos du profil (MODIFIÉ)
    total_games = len(df)
    winrate = (df['winner'].sum() / total_games) * 100

    # --- NOUVELLE LOGIQUE POUR RÔLES ---
    role_counts = df['position'].value_counts()
    main_role = role_counts.index[0] if not role_counts.empty else "Inconnu"
    secondary_role = role_counts.index[1] if len(role_counts) > 1 else "Aucun"

    # --- NOUVELLE LOGIQUE POUR CHAMPIONS ---
    champion_counts = df['champion'].value_counts()
    # Prend le top 3 et le convertit en liste de dictionnaires
    top_champions = [
        {"name": champ, "count": int(count)}
        for champ, count in champion_counts.head(3).items()
    ]

    # 5. Récupérer les features RLS (inchangé)
    active_features_config = get_active_features()
    features_for_role = active_features_config.get(
        main_role, ["kda", "gold_per_min"])

    role_specific_avg_stats = {}
    for feature in features_for_role:
        if feature in df.columns:
            role_specific_avg_stats[feature] = df[feature].mean()
        else:
            role_specific_avg_stats[feature] = 0.0

    # 6. Retourner le profil complet (MODIFIÉ)
    return {
        "riot_id": riot_id,
        "mu": mu,
        "sigma": sigma,
        "total_games": total_games,
        "winrate": winrate,
        "main_role": main_role,
        "secondary_role": secondary_role,   # AJOUT
        "top_champions": top_champions,     # AJOUT
        "role_specific_avg_stats": role_specific_avg_stats
    }
