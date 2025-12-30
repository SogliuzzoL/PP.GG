import numpy as np
import pandas as pd

from backend.app.utils.db import get_db_connection


class MatchRepository:
    def create_match(self, duration_min, winner_side):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "INSERT INTO matches (game_duration, winner, created_at) VALUES (?, ?, DATETIME('now'))",
            (duration_min, winner_side)
        )
        match_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return match_id

    def add_player_stats(self, match_id, player_id, stats_dict):
        conn = get_db_connection()
        valid_columns = [
            "champion_name", "team_side", "role", "is_winner",
            "kills", "deaths", "assists", "total_team_kills", "cs", "gold_earned",
            "total_damage_dealt_to_champions", "total_team_damage", "vision_score",
            "wards_killed", "vision_wards_bought_in_game", "time_ccing_others",
            "total_heal_on_teammates", "total_damage_shielded_on_teammates",
            "total_damage_self_mitigated", "total_heal"
        ]

        filtered_stats = {k: v for k,
                          v in stats_dict.items() if k in valid_columns}

        cols = ', '.join(filtered_stats.keys())
        placeholders = ', '.join(['?'] * len(filtered_stats))
        vals = list(filtered_stats.values())

        query = f"INSERT INTO player_match_stats (match_id, player_id, {cols}) VALUES (?, ?, {placeholders})"
        conn.execute(query, [match_id, player_id] + vals)
        conn.commit()
        conn.close()

    def get_historical_data_dataframe(self):
        """Récupère tout l'historique, calcule les métriques /min et nettoie les brutes."""
        conn = get_db_connection()
        query = """
        SELECT pms.*, m.game_duration
        FROM player_match_stats pms
        JOIN matches m ON pms.match_id = m.match_id
        """
        try:
            df = pd.read_sql_query(query, conn)

            if df.empty:
                return df

            # Sécurité divisions par zéro
            df['game_duration'] = df['game_duration'].replace(0, 1)
            df['deaths'] = df['deaths'].replace(0, 1)
            df['total_team_kills'] = df['total_team_kills'].replace(0, 1)
            df['total_team_damage'] = df['total_team_damage'].replace(0, 1)

            # --- 1. Ratios ---
            df['kda'] = (df['kills'] + df['assists']) / df['deaths']
            df['kill_participation'] = (
                (df['kills'] + df['assists']) / df['total_team_kills']) * 100
            df['team_damage_percentage'] = (
                df['total_damage_dealt_to_champions'] / df['total_team_damage']) * 100

            # --- 2. Normalisation par Minute ---
            df['kills_per_min'] = df['kills'] / df['game_duration']
            df['deaths_per_min'] = df['deaths'] / df['game_duration']
            df['assists_per_min'] = df['assists'] / df['game_duration']

            df['cs_per_min'] = df['cs'] / df['game_duration']
            df['gold_per_min'] = df['gold_earned'] / df['game_duration']
            df['damage_dealt_per_min'] = df['total_damage_dealt_to_champions'] / \
                df['game_duration']
            df['vision_score_per_min'] = df['vision_score'] / df['game_duration']
            df['cc_score_per_min'] = df['time_ccing_others'] / df['game_duration']
            df['healing_on_teammates_per_min'] = df['total_heal_on_teammates'] / \
                df['game_duration']
            df['shields_on_teammates_per_min'] = df['total_damage_shielded_on_teammates'] / \
                df['game_duration']

            df['effective_tanking_per_min'] = (
                df['total_damage_self_mitigated'] +
                (df['total_heal'] - df['total_heal_on_teammates'])
            ) / df['game_duration']

            df['vision_control_per_min'] = (
                df['wards_killed'] * 1.5 + df['vision_wards_bought_in_game']
            ) / df['game_duration']

            # Target pour XGBoost
            if 'is_winner' in df.columns:
                df['win'] = df['is_winner'].astype(int)

            # --- 3. Nettoyage ---
            # CORRECTION : On NE SUPPRIME PAS 'match_id', 'player_id' ici car le retraining en a besoin
            cols_to_drop = [
                'kills', 'deaths', 'assists',
                'cs', 'gold_earned',
                'total_damage_dealt_to_champions', 'total_team_damage',
                'vision_score', 'time_ccing_others',
                'total_heal_on_teammates', 'total_damage_shielded_on_teammates',
                'total_damage_self_mitigated', 'total_heal',
                'wards_killed', 'vision_wards_bought_in_game',
                'total_team_kills',
                'champion_name', 'team_side', 'is_winner'
            ]
            df.drop(
                columns=[c for c in cols_to_drop if c in df.columns], inplace=True)

        except Exception as e:
            print(f"Erreur chargement DF: {e}")
            df = pd.DataFrame()
        finally:
            conn.close()

        return df
