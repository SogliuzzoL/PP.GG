import datetime

import requests

from backend.app.repositories.match_repository import MatchRepository
from backend.app.repositories.player_repository import PlayerRepository
from backend.app.services.analytics_service import AnalyticsService
from backend.app.services.scoring_service import ScoringService
from backend.config import Config


class MatchService:
    def __init__(self):
        self.match_repo = MatchRepository()
        self.player_repo = PlayerRepository()
        self.scoring_service = ScoringService()
        self.analytics_service = AnalyticsService()

    def process_match(self, match_data):
        # ... Extraction données (identique) ...
        duration = match_data.get("gameLength", 1) / 60.0
        teams = match_data["teams"]
        is_blue_winner = (teams[0]["isBottomTeam"] and teams[0]["isWinningTeam"]) or \
                         (not teams[0]["isBottomTeam"]
                          and not teams[0]["isWinningTeam"])
        winner_side = "bot" if is_blue_winner else "top"

        match_id = self.match_repo.create_match(duration, winner_side)

        players_processing_list = []
        avg_skill_acc = 0

        for team in teams:
            team_side_code = "bot" if team["isBottomTeam"] else "top"
            display_side = "Blue" if team["isBottomTeam"] else "Red"
            is_winner = (team_side_code == winner_side)

            team_dmg = sum(p["stats"].get(
                "TOTAL_DAMAGE_DEALT_TO_CHAMPIONS", 0) for p in team["players"])
            team_kills = sum(p["stats"].get("CHAMPIONS_KILLED", 0)
                             for p in team["players"])

            for p_raw in team["players"]:
                # ... Gestion Identité (identique) ...
                puuid = p_raw["puuid"]
                riot_id = f"{p_raw['riotIdGameName']}#{p_raw['riotIdTagLine']}"
                pid = self.player_repo.get_player_id(puuid)
                if not pid:
                    pid = self.player_repo.create_player(puuid, riot_id)
                else:
                    self.player_repo.update_riot_id(pid, riot_id)

                stats = p_raw.get("stats", {})
                role = p_raw.get("detectedTeamPosition", "UTILITY")
                if role == "MID":
                    role = "MIDDLE"
                if role in ["SUPPORT", "SUPP", "UTILITY"]:
                    role = "UTILITY"
                if role == "UNKNOWN":
                    role = "UTILITY"

                # ... Calcul Metrics (identique) ...
                metrics = {
                    "kda": (stats.get("CHAMPIONS_KILLED", 0) + stats.get("ASSISTS", 0)) / max(1, stats.get("NUM_DEATHS", 1)),
                    "kills_per_min": stats.get("CHAMPIONS_KILLED", 0) / duration,
                    "deaths_per_min": stats.get("NUM_DEATHS", 0) / duration,
                    "assists_per_min": stats.get("ASSISTS", 0) / duration,
                    "gold_per_min": stats.get("GOLD_EARNED", 0) / duration,
                    "damage_dealt_per_min": stats.get("TOTAL_DAMAGE_DEALT_TO_CHAMPIONS", 0) / duration,
                    "vision_score_per_min": stats.get("VISION_SCORE", 0) / duration,
                    "vision_control_per_min": (stats.get("WARD_KILLED", 0) * 1.5 + stats.get("VISION_WARDS_BOUGHT_IN_GAME", 0)) / duration,
                    "cs_per_min": (stats.get("MINIONS_KILLED", 0) + stats.get("NEUTRAL_MINIONS_KILLED", 0)) / duration,
                    "kill_participation": (stats.get("CHAMPIONS_KILLED", 0) + stats.get("ASSISTS", 0)) / max(1, team_kills) * 100,
                    "team_damage_percentage": (stats.get("TOTAL_DAMAGE_DEALT_TO_CHAMPIONS", 0) / max(1, team_dmg)) * 100,
                    "cc_score_per_min": stats.get("TIME_CCING_OTHERS", 0) / duration,
                    "healing_on_teammates_per_min": stats.get("TOTAL_HEAL_ON_TEAMMATES", 0) / duration,
                    "shields_on_teammates_per_min": stats.get("TOTAL_DAMAGE_SHIELDED_ON_TEAMMATES", 0) / duration,
                    "effective_tanking_per_min": (stats.get("TOTAL_DAMAGE_SELF_MITIGATED", 0) + (stats.get("TOTAL_HEAL", 0) - stats.get("TOTAL_HEAL_ON_TEAMMATES", 0))) / duration,
                }

                # ... DB Stats (identique) ...
                db_stats = {
                    "champion_name": p_raw.get("championName"),
                    "team_side": team_side_code,
                    "role": role,
                    "is_winner": 1 if is_winner else 0,
                    "kills": stats.get("CHAMPIONS_KILLED", 0),
                    "deaths": stats.get("NUM_DEATHS", 0),
                    "assists": stats.get("ASSISTS", 0),
                    "total_team_kills": team_kills,
                    "cs": stats.get("MINIONS_KILLED", 0) + stats.get("NEUTRAL_MINIONS_KILLED", 0),
                    "gold_earned": stats.get("GOLD_EARNED", 0),
                    "total_damage_dealt_to_champions": stats.get("TOTAL_DAMAGE_DEALT_TO_CHAMPIONS", 0),
                    "total_team_damage": team_dmg,
                    "vision_score": stats.get("VISION_SCORE", 0),
                    "wards_killed": stats.get("WARD_KILLED", 0),
                    "vision_wards_bought_in_game": stats.get("VISION_WARDS_BOUGHT_IN_GAME", 0),
                    "time_ccing_others": stats.get("TIME_CCING_OTHERS", 0),
                    "total_heal_on_teammates": stats.get("TOTAL_HEAL_ON_TEAMMATES", 0),
                    "total_damage_shielded_on_teammates": stats.get("TOTAL_DAMAGE_SHIELDED_ON_TEAMMATES", 0),
                    "total_damage_self_mitigated": stats.get("TOTAL_DAMAGE_SELF_MITIGATED", 0),
                    "total_heal": stats.get("TOTAL_HEAL", 0)
                }
                self.match_repo.add_player_stats(match_id, pid, db_stats)

                curr_skill = self.player_repo.get_skill(pid)
                avg_skill_acc += curr_skill[0] if curr_skill else 50.0

                players_processing_list.append({
                    "player_id": pid,
                    "riot_id": riot_id,
                    "role": role,
                    "is_winner": is_winner,
                    "metrics": metrics,
                    "team_side": team_side_code,
                    "display_side": display_side,
                    "champion": p_raw.get("championName")
                })

        # Orchestration
        hist_df = self.match_repo.get_historical_data_dataframe()
        self.scoring_service.ensure_models_up_to_date(hist_df)

        # 1. Calcul RLS
        players_processing_list = self.scoring_service.calculate_match_scores(
            players_processing_list)
        # 2. Calcul XGBoost
        players_processing_list = self.analytics_service.compute_shadow_scores(
            match_id, players_processing_list)

        # 3. Mise à jour MMR (avec XGBoost)
        avg_match_skill = avg_skill_acc / \
            len(players_processing_list) if players_processing_list else 50.0
        final_players = self.scoring_service.update_player_skills(
            players_processing_list, avg_match_skill, score_key='shadow_score')

        # 4. Update RLS (Background)
        self.scoring_service.update_rls_weights(final_players)

        # 5. Webhook
        self._send_discord_webhook(
            match_id, winner_side, duration, final_players)

        return {"match_id": match_id, "status": "success"}

    def _send_discord_webhook(self, match_id, winner, duration, players):
        if not Config.DISCORD_WEBHOOK_URL:
            return

        roles_order = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]
        blue_team_map = {
            p['role']: p for p in players if p['display_side'] == "Blue"}
        red_team_map = {
            p['role']: p for p in players if p['display_side'] == "Red"}

        col_blue_text, col_red_text = "", ""

        for role in roles_order:
            role_icon = self._get_role_icon(role)
            col_blue_text += self._format_player_block(
                blue_team_map.get(role), role_icon) + "\n"
            col_red_text += self._format_player_block(
                red_team_map.get(role), role_icon) + "\n"

        winner_display = "BLUE" if winner == "bot" else "RED"
        color = 5763719 if winner_display == "BLUE" else 15548997

        embed = {
            "title": f"🏆 Rapport de Match #{match_id}",
            "description": f"**Vainqueur:** {winner_display} Side • ⏱️ **{int(duration)} min**",
            "color": color,
            "fields": [
                {"name": "🔵 Équipe Bleue", "value": col_blue_text, "inline": True},
                {"name": "🔴 Équipe Rouge", "value": col_red_text, "inline": True}
            ],
            "footer": {"text": "PP.GG v2 • Powered by XGBoost"},
            "timestamp": datetime.datetime.utcnow().isoformat()
        }

        try:
            requests.post(Config.DISCORD_WEBHOOK_URL, json={"embeds": [embed]})
        except Exception as e:
            print(f"❌ Erreur Discord: {e}")

    def _format_player_block(self, p, role_icon):
        if not p:
            return f"{role_icon} **AFK**\n-\n-\n"

        xgb = p.get('shadow_score', 0)
        rls = p.get('normalized_score', 50)

        delta = xgb - rls
        trend = "➖"
        if delta > 5:
            trend = "📈"
        elif delta < -5:
            trend = "📉"

        # Rating Update
        old_rating = p.get('old_mu', 50.0)
        new_rating = p.get('new_mu', 50.0)
        diff = new_rating - old_rating
        diff_str = f"+{diff:.1f}" if diff > 0 else f"{diff:.1f}"

        m = p['metrics']
        stats = f"KDA: {m['kda']:.1f} • DPM: {int(m['damage_dealt_per_min'])}"

        l1 = f"{role_icon} **{p['riot_id']}**"
        l2 = f"👨‍🦯 Champion: **{p.get('champion', '?')}**"
        l3 = f"📊 Rating: **{xgb:.1f}** `(Legacy: {rls:.0f} {trend})`"
        l4 = f"📈 MMR: {old_rating:.1f} ➜ **{new_rating:.1f}** ({diff_str})"
        l5 = f"⚔️ {stats}"

        return f"{l1}\n{l2}\n{l3}\n{l4}\n{l5}\n"

    def _get_role_icon(self, role):
        icons = {"TOP": "🛡️", "JUNGLE": "🌲",
                 "MIDDLE": "🔥", "BOTTOM": "🏹", "UTILITY": "💖"}
        return icons.get(role, "❓")
