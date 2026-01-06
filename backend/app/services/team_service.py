import datetime
import itertools

import requests

from backend.app.repositories.player_repository import PlayerRepository
from backend.config import Config


class TeamService:
    def __init__(self):
        self.player_repo = PlayerRepository()

    def balance_teams(self, player_names):
        # 1. Récupérer les données des joueurs
        players_data = self.player_repo.get_players_batch(player_names)

        # Créer une map pour accès rapide
        players_map = {p['riot_id']: p for p in players_data}
        full_players = []

        for name in player_names:
            p_data = players_map.get(name)
            # Calcul du Rating: mu - 3*sigma (Rating conservateur "TrueSkill")
            if p_data and p_data['mu'] is not None:
                rating = p_data['mu'] - 3 * p_data['sigma']
                real_mu = p_data['mu']
            else:
                # Valeur par défaut pour les nouveaux
                rating = 0.0
                real_mu = 50.0  # Rating moyen pour l'affichage interne

            full_players.append({
                'riot_id': name,
                'rating': rating,
                'mu': real_mu
            })

        # 2. Vérification
        if len(full_players) < 2:
            return {"error": "Il faut au moins 2 joueurs pour équilibrer."}

        # 3. Algorithme de Brute-Force (Combinatoire)
        n = len(full_players)
        team_size = n // 2

        all_players_indices = set(range(n))
        best_diff = float('inf')
        best_teams = ([], [])

        # Génère toutes les combinaisons pour l'équipe 1
        for team1_indices in itertools.combinations(all_players_indices, team_size):
            team1_indices = set(team1_indices)
            team2_indices = all_players_indices - team1_indices

            team1 = [full_players[i] for i in team1_indices]
            team2 = [full_players[i] for i in team2_indices]

            avg1 = sum(p['rating'] for p in team1) / len(team1)
            avg2 = sum(p['rating'] for p in team2) / len(team2) if team2 else 0

            diff = abs(avg1 - avg2)

            if diff < best_diff:
                best_diff = diff
                best_teams = (team1, team2)

        result = {
            "team1": best_teams[0],
            "team2": best_teams[1],
            "rating_diff": best_diff,
            "avg_team1": sum(p['rating'] for p in best_teams[0]) / len(best_teams[0]),
            "avg_team2": sum(p['rating'] for p in best_teams[1]) / len(best_teams[1])
        }

        # 4. ENVOI DU WEBHOOK
        self._send_discord_webhook(result)

        return result

    def _send_discord_webhook(self, data):
        """Envoie un embed Discord avec les équipes générées."""
        webhook_url = Config.DISCORD_WEBHOOK_URL
        if not webhook_url:
            print("⚠️ Pas de Webhook configuré dans le .env")
            return

        t1 = data['team1']
        t2 = data['team2']
        avg1 = data['avg_team1']
        avg2 = data['avg_team2']
        diff = data['rating_diff']

        # Formatage du texte pour chaque équipe
        def format_team(team_list):
            # Trie les joueurs par rating décroissant pour l'affichage
            sorted_team = sorted(
                team_list, key=lambda x: x['rating'], reverse=True)
            return "\n".join([f"• **{p['riot_id']}** `({p['rating']:.2f})`" for p in sorted_team])

        col_blue = format_team(t1)
        col_red = format_team(t2)

        # Choix de la couleur et du message de footer selon l'équilibre
        color = 5763719  # Bleu par défaut
        footer_msg = "Généré via PP.GG Auto-Balance"

        if diff < 5:
            footer_msg += " • 🔥 Match très équilibré !"
            color = 5763719  # Green/Blue
        elif diff > 20:
            footer_msg += " • ⚠️ Déséquilibre détecté"
            color = 15548997  # Red

        embed = {
            "title": "⚖️ Équipes Équilibrées (Lobby)",
            "description": f"Voici la meilleure combinaison possible trouvée par l'algorithme.\n**Écart de niveau :** `{diff:.2f}`",
            "color": color,
            "fields": [
                {
                    "name": f"🔵 Équipe 1 (Moy: {avg1:.2f})",
                    "value": col_blue if col_blue else "Vide",
                    "inline": True
                },
                {
                    "name": f"🔴 Équipe 2 (Moy: {avg2:.2f})",
                    "value": col_red if col_red else "Vide",
                    "inline": True
                }
            ],
            "footer": {"text": footer_msg},
            "timestamp": datetime.datetime.utcnow().isoformat()
        }

        try:
            requests.post(webhook_url, json={"embeds": [embed]})
            print("✅ Webhook envoyé avec succès.")
        except Exception as e:
            print(f"❌ Erreur lors de l'envoi du webhook: {e}")
