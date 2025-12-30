import pandas as pd

from backend.app.repositories.player_repository import PlayerRepository


class PlayerService:
    def __init__(self):
        self.player_repo = PlayerRepository()

    def get_player_profile(self, riot_id):
        history_data, player_id = self.player_repo.get_player_stats_history(
            riot_id)
        if not history_data:
            return None

        df = pd.DataFrame(history_data)

        if 'position' in df.columns:
            df.rename(columns={'position': 'role'}, inplace=True)

        skill = self.player_repo.get_skill(player_id)
        mu, sigma = skill if skill else (50.0, 16.66)

        total_games = len(df)
        wins = df['is_winner'].sum()
        winrate = (wins / total_games * 100) if total_games > 0 else 0

        # Utilisation de 'role'
        role_counts = df['role'].value_counts()
        main_role = role_counts.index[0] if not role_counts.empty else "UNKNOWN"
        secondary_role = role_counts.index[1] if len(
            role_counts) > 1 else "Aucun"

        champ_stats = df.groupby('champion_name').agg(
            count=('match_id', 'count'),
            wins=('is_winner', 'sum')
        ).reset_index()
        champ_stats['winrate'] = (
            champ_stats['wins'] / champ_stats['count'] * 100)
        top_champions = champ_stats.sort_values(
            by='count', ascending=False).head(5).to_dict('records')

        def get_avg_stats(role_name):
            if role_name == "Aucun":
                return {}
            # Utilisation de 'role'
            role_df = df[df['role'] == role_name]
            if role_df.empty:
                return {}

            metrics = [
                'kda', 'kill_participation', 'cs_per_min', 'gold_per_min',
                'damage_dealt_per_min', 'vision_score_per_min', 'cc_score_per_min',
                'healing_on_teammates_per_min', 'shields_on_teammates_per_min',
                'effective_tanking_per_min'
            ]
            valid_metrics = [m for m in metrics if m in role_df.columns]
            return role_df[valid_metrics].mean().to_dict()

        return {
            "riot_id": riot_id,
            "rating": mu - 3 * sigma,
            "mu": mu,
            "sigma": sigma,
            "total_games": total_games,
            "winrate": winrate,
            "main_role": main_role,
            "secondary_role": secondary_role,
            "top_champions": [{"name": c['champion_name'], "count": c['count'], "winrate": c['winrate']} for c in top_champions],
            "role_specific_avg_stats": get_avg_stats(main_role),
            "secondary_role_avg_stats": get_avg_stats(secondary_role)
        }
