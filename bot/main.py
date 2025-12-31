import base64
import io
import json
import os

import discord
import requests
from discord import app_commands
from discord.ext import commands
from dotenv import load_dotenv

# Load environment variables from .env file
load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '..', '.env'))
TOKEN = os.getenv('discord_token')
# Default to localhost if not set
BACKEND_URL = os.getenv('backend_url')

# Define intents
intents = discord.Intents.default()
intents.message_content = True  # Required for message content access in some cases

# Create bot instance
bot = commands.Bot(command_prefix="!", intents=intents)


class AnalysisView(discord.ui.View):
    def __init__(self, riot_id, role):
        super().__init__(timeout=None)  # Timeout None pour que le bouton reste actif
        self.riot_id = riot_id
        self.role = role

    @discord.ui.button(label="🧠 Analyse IA Détaillée", style=discord.ButtonStyle.blurple, emoji="📊")
    async def analyze_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer(thinking=True)

        # Appel au backend (Attention : ça peut prendre 2-3 secondes)
        try:
            params = {'riot_id': self.riot_id, 'role': self.role}
            response = requests.get(
                f"{BACKEND_URL}/personal_meta", params=params)

            if response.status_code != 200:
                err = response.json().get('error', 'Erreur inconnue')
                await interaction.followup.send(f"❌ {err}", ephemeral=True)
                return

            data = response.json()
            image_b64 = data.get('image_base64')
            tips = data.get('text_analysis', [])

            # Décodage image
            image_bytes = base64.b64decode(image_b64)
            file = discord.File(io.BytesIO(image_bytes),
                                filename="personal_shap.png")

            embed = discord.Embed(
                title=f"🧠 Pourquoi {self.riot_id} gagne (ou perd) ?",
                description="Ce graphique montre l'impact précis de tes stats moyennes sur ta probabilité de victoire par rapport à la moyenne du serveur.",
                color=discord.Color.purple()
            )
            embed.set_image(url="attachment://personal_shap.png")

            if tips:
                embed.add_field(name="📋 Conclusions",
                                value="\n".join(tips), inline=False)

            embed.set_footer(
                text="Basé sur un modèle XGBoost personnalisé vs Base Value")

            await interaction.followup.send(embed=embed, file=file)

        except Exception as e:
            await interaction.followup.send(f"Une erreur est survenue : {e}", ephemeral=True)


class TopPlayersPaginator(discord.ui.View):
    def __init__(self, interaction: discord.Interaction, limit: int = 10):
        super().__init__(timeout=180)
        self.interaction = interaction
        self.message = None
        self.current_offset = 0
        self.limit = limit

    async def fetch_players(self, offset: int):
        """Fetches player data from the backend."""
        try:
            response = requests.get(
                f"{BACKEND_URL}/top_players?limit={self.limit}&offset={offset}")
            response.raise_for_status()
            data = response.json()
            print(f"Fetched players data: {data}")
            return data.get('top_players')
        except requests.exceptions.RequestException as e:
            print(f"Error fetching players: {e}")
            return None

    async def create_embed(self, players_data):
        embed = discord.Embed(
            title=f"🏆 Top Players - Page {self.current_offset // self.limit + 1}",
            # Une couleur sombre (Dark theme) ou .blue()
            color=discord.Color.from_rgb(47, 49, 54)
        )

        if not players_data:
            embed.description = "Il n'y a plus de joueurs à afficher."
        else:
            for i, player in enumerate(players_data, start=1+self.current_offset):
                riot_id = player.get('riot_id', 'Unknown#')
                # On garde ta logique exacte pour le nom
                game_name, tag_line = riot_id.split(
                    '#', 1) if '#' in riot_id else (riot_id, '')

                # Médailles
                rank_map = {1: "🥇", 2: "🥈", 3: "🥉"}
                rank_emoji = rank_map.get(i, f"**#{i}**")

                rating = player.get('rating', 0)
                mu = player.get('mu', 0)
                sigma = player.get('sigma', 0)

                # LE CHANGEMENT EST ICI :
                # On met le nom en clair dans le titre du field
                # On utilise ">" pour créer un bloc "citation" qui contient les stats
                # On met le Rating entre ` ` pour le faire ressortir comme un bouton
                embed.add_field(
                    name=f"{rank_emoji} • {game_name}#{tag_line}",
                    value=f"> 🛡️ Rating: `{rating:.2f}`\n> *μ={mu:.1f} • σ={sigma:.1f}*",
                    inline=False
                )
        return embed

    async def update_message(self):
        """Updates the original message with the new page."""
        players = await self.fetch_players(self.current_offset)
        embed = await self.create_embed(players)

        # Disable 'Previous' on first page
        self.children[0].disabled = self.current_offset == 0
        # Disable 'Next' if there are no more players
        self.children[1].disabled = not players or len(players) < self.limit

        await self.message.edit(embed=embed, view=self)

    @discord.ui.button(label="⬅️ Précédent", style=discord.ButtonStyle.grey)
    async def previous_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        if self.current_offset > 0:
            self.current_offset -= self.limit
            await self.update_message()

    @discord.ui.button(label="Suivant ➡️", style=discord.ButtonStyle.grey)
    async def next_button(self, interaction: discord.Interaction, button: discord.ui.Button):
        await interaction.response.defer()
        self.current_offset += self.limit
        await self.update_message()


@bot.event
async def on_ready():
    print(f'Logged in as {bot.user} (ID: {bot.user.id})')
    print('------')
    try:
        synced = await bot.tree.sync()
        print(f"Synced {len(synced)} command(s)")
    except Exception as e:
        print(e)


@bot.tree.command(name="top", description="Affiche le classement des joueurs avec pagination")
async def top(interaction: discord.Interaction):
    """Shows the top players with pagination."""
    await interaction.response.defer()

    paginator = TopPlayersPaginator(interaction)

    # Fetch initial data and send the first page
    initial_players = await paginator.fetch_players(0)
    initial_embed = await paginator.create_embed(initial_players)

    # Disable previous button on first load
    paginator.children[0].disabled = True
    # Disable next if there are no more players
    if not initial_players or len(initial_players) < paginator.limit:
        paginator.children[1].disabled = True

    paginator.message = await interaction.followup.send(embed=initial_embed, view=paginator)


@bot.tree.command(name="weights", description="Affiche les poids de performance actuels")
async def weights(interaction: discord.Interaction):
    """Sends a request to the backend to get the performance weights."""
    await interaction.response.defer()
    try:
        response = requests.get(f"{BACKEND_URL}/get_weights")
        response.raise_for_status()  # Raise an exception for bad status codes
        data = response.json()
        print(f"Fetched weights data: {data}")

        # Format the data for display
        embed = discord.Embed(title="Performance Weights",
                              color=discord.Color.green())

        # Assuming the weights are returned under a 'weights' key
        weights_data = data.get('weights', {})
        for role, stats in weights_data.items():
            if isinstance(stats, dict):
                # If the value is a dictionary, format its contents
                value_str = "\n".join(
                    [f"{k.replace('_', ' ').title()}: {v:.4f}" for k, v in stats.items() if v != 0])
                embed.add_field(name=role.replace('_', ' ').title(),
                                value=value_str, inline=False)
            else:
                # This part might not be needed if the structure is consistent
                embed.add_field(name=role.replace('_', ' ').title(),
                                value=f"{stats:.4f}", inline=True)

        await interaction.followup.send(embed=embed)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send(f"Erreur lors de la récupération des données du backend: {e}")
    except Exception as e:
        await interaction.followup.send(f"Une erreur est survenue: {e}")


@bot.tree.command(name="stat", description="Affiche les statistiques d'un joueur")
@app_commands.describe(joueur="Le Riot ID complet du joueur (ex: MonPseudo#EUW)")
async def stat(interaction: discord.Interaction, joueur: str):
    """Affiche les statistiques détaillées d'un joueur."""
    await interaction.response.defer()

    params = {'riot_id': joueur}

    try:
        response = requests.get(f"{BACKEND_URL}/player_stats", params=params)

        if response.status_code == 404:
            await interaction.followup.send(f"❌ Joueur non trouvé : `{joueur}`. Avez-vous bien inclus le tagline (ex: #EUW) ?")
            return

        response.raise_for_status()
        data = response.json()

        # --- AMÉLIORATION ESTHÉTIQUE ---

        # 1. Couleur dynamique basée sur le Winrate
        winrate = data.get('winrate', 0)
        color = discord.Color.green() if winrate >= 50.0 else discord.Color.red()

        embed = discord.Embed(
            title=f"Statistiques pour {data.get('riot_id', joueur)}",
            color=color
        )

        # 2. Layout 2x2 (inline=True pour les deux premiers, puis les deux suivants)
        embed.add_field(
            name="📈 Classement (MMR)",
            value=f"**Rating**: `{data.get('rating', 0):.2f}`\n**μ (Niveau)**: `{data.get('mu', 0):.2f}`\n**σ (Confiance)**: `{data.get('sigma', 0):.2f}`",
            inline=True
        )

        embed.add_field(
            name="🎮 Activité",
            value=f"**Parties jouées**: `{data.get('total_games', 0)}`\n**Winrate**: `{winrate:.1f}%`",
            inline=True
        )

        embed.add_field(
            name="🛡️ Rôles",
            value=f"**Main**: {data.get('main_role', 'Inconnu')}\n**Secondaire**: {data.get('secondary_role', 'Aucun')}",
            inline=True
        )

        top_champions = data.get('top_champions', [])
        if top_champions:
            champ_list = [
                f"**1.** {top_champions[0]['name']} ({top_champions[0]['count']} p.) - {top_champions[0]['winrate']:.1f}% winrate"
            ]
            if len(top_champions) > 1:
                champ_list.append(
                    f"**2.** {top_champions[1]['name']} ({top_champions[1]['count']} p.) - {top_champions[1]['winrate']:.1f}% winrate")
            if len(top_champions) > 2:
                champ_list.append(
                    f"**3.** {top_champions[2]['name']} ({top_champions[2]['count']} p.) - {top_champions[2]['winrate']:.1f}% winrate")
            if len(top_champions) > 3:
                champ_list.append(
                    f"**4.** {top_champions[3]['name']} ({top_champions[3]['count']} p.) - {top_champions[3]['winrate']:.1f}% winrate")
            if len(top_champions) > 4:
                champ_list.append(
                    f"**5.** {top_champions[4]['name']} ({top_champions[4]['count']} p.) - {top_champions[4]['winrate']:.1f}% winrate")

            embed.add_field(
                name="🏆 Top Champions",
                value="\n".join(champ_list),
                inline=True
            )
        else:
            embed.add_field(name="🏆 Top Champions",
                            value="Aucun match joué", inline=True)

        # # 3. Séparateur pleine largeur
        # embed.add_field(name="\u200b", value="\u200b", inline=False)

        # # 4. Section des moyennes (avec formatage amélioré)
        # role_stats = data.get('role_specific_avg_stats', {})

        # if role_stats:
        #     stats_list = []
        #     # Dictionnaire pour de plus jolis noms
        #     pretty_names = {
        #         "kda": "KDA", "kill_participation": "KP%", "cs_per_min": "CS/min",
        #         "gold_per_min": "Gold/min", "damage_dealt_per_min": "Dégâts/min",
        #         "vision_score_per_min": "Vision/min", "cc_score_per_min": "CC/min",
        #         "healing_on_teammates_per_min": "Heal(Alliés)/min",
        #         "shields_on_teammates_per_min": "Shield(Alliés)/min",
        #         "effective_tanking_per_min": "Tanking/min"
        #     }

        #     for stat_name, stat_value in role_stats.items():
        #         display_name = pretty_names.get(
        #             stat_name, stat_name.replace('_', ' ').title())

        #         # 5. Formatage des chiffres (arrondis, %, etc.)
        #         if "kda" in stat_name:
        #             value = f"{stat_value:.2f}"
        #         elif "participation" in stat_name:
        #             value = f"{stat_value:.1f}%"
        #         elif "damage_dealt" in stat_name or "tanking" in stat_name:
        #             # Pas de décimale pour les gros chiffres
        #             value = f"{stat_value:.0f}"
        #         else:
        #             value = f"{stat_value:.1f}"  # 1 décimale pour le reste

        #         stats_list.append(f"**{display_name}**: `{value}`")

        #     if stats_list:
        #         title = f"📊 Moyennes (Rôle: {data.get('main_role')})"

        #         # Divise en deux colonnes si + de 3 stats
        #         if len(stats_list) > 3:
        #             mid_point = (len(stats_list) + 1) // 2
        #             col1 = "\n".join(stats_list[:mid_point])
        #             col2 = "\n".join(stats_list[mid_point:])

        #             embed.add_field(name=title, value=col1, inline=True)
        #             embed.add_field(name="\u200b", value=col2,
        #                             inline=True)  # Nom invisible
        #         else:
        #             embed.add_field(name=title, value="\n".join(
        #                 stats_list), inline=False)

        # embed.add_field(name="\u200b", value="\u200b", inline=False)

        # secondary_role_stats = data.get('secondary_role_avg_stats', {})

        # if secondary_role_stats:
        #     stats_list = []
        #     # Dictionnaire pour de plus jolis noms
        #     pretty_names = {
        #         "kda": "KDA", "kill_participation": "KP%", "cs_per_min": "CS/min",
        #         "gold_per_min": "Gold/min", "damage_dealt_per_min": "Dégâts/min",
        #         "vision_score_per_min": "Vision/min", "cc_score_per_min": "CC/min",
        #         "healing_on_teammates_per_min": "Heal(Alliés)/min",
        #         "shields_on_teammates_per_min": "Shield(Alliés)/min",
        #         "effective_tanking_per_min": "Tanking/min"
        #     }

        #     for stat_name, stat_value in secondary_role_stats.items():
        #         display_name = pretty_names.get(
        #             stat_name, stat_name.replace('_', ' ').title())

        #         # 5. Formatage des chiffres (arrondis, %, etc.)
        #         if "kda" in stat_name:
        #             value = f"{stat_value:.2f}"
        #         elif "participation" in stat_name:
        #             value = f"{stat_value:.1f}%"
        #         elif "damage_dealt" in stat_name or "tanking" in stat_name:
        #             # Pas de décimale pour les gros chiffres
        #             value = f"{stat_value:.0f}"
        #         else:
        #             value = f"{stat_value:.1f}"  # 1 décimale pour le reste

        #         stats_list.append(f"**{display_name}**: `{value}`")

        #     if stats_list:
        #         title = f"📊 Moyennes (Rôle Secondaire: {data.get('secondary_role')})"

        #         # Divise en deux colonnes si + de 3 stats
        #         if len(stats_list) > 3:
        #             mid_point = (len(stats_list) + 1) // 2
        #             col1 = "\n".join(stats_list[:mid_point])
        #             col2 = "\n".join(stats_list[mid_point:])

        #             embed.add_field(name=title, value=col1, inline=True)
        #             embed.add_field(name="\u200b", value=col2,
        #                             inline=True)  # Nom invisible
        #         else:
        #             embed.add_field(name=title, value="\n".join(
        #                 stats_list), inline=False)

        embed.set_footer(
            text="Statistiques basées sur l'historique de toutes les parties PP.GG")

        # 1. Déterminer le rôle principal pour le bouton
        main_role = data.get('main_role', 'UNKNOWN')

        # 2. Créer la vue si le rôle est valide
        view = None
        if main_role and main_role != 'Inconnu':
            # Mapping des rôles si nécessaire, ou on passe direct si le backend gère "JUNGLE" etc.
            view = AnalysisView(riot_id=data.get(
                'riot_id', joueur), role=main_role)

        # 3. Envoyer avec la view
        await interaction.followup.send(embed=embed, view=view)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send(f"Erreur lors de la connexion au backend : {e}")
    except Exception as e:
        await interaction.followup.send(f"Une erreur inattendue est survenue : {e}")


@bot.tree.command(name="meta", description="Analyse la méta actuelle (XGBoost) pour un rôle : quoi jouer pour gagner ?")
@app_commands.describe(role="Le rôle à analyser")
@app_commands.choices(role=[
    app_commands.Choice(name="Toplane", value="TOP"),
    app_commands.Choice(name="Jungle", value="JUNGLE"),
    app_commands.Choice(name="Midlane", value="MIDDLE"),
    app_commands.Choice(name="ADC (Bot)", value="BOTTOM"),
    app_commands.Choice(name="Support", value="UTILITY"),
])
async def meta(interaction: discord.Interaction, role: app_commands.Choice[str]):
    """Affiche l'analyse SHAP et les conseils tactiques pour un rôle."""
    await interaction.response.defer()
    selected_role = role.value  # ex: "JUNGLE"

    try:
        # Appel à la route backend créée précédemment
        response = requests.get(f"{BACKEND_URL}/meta/{selected_role}")

        # Gestion du cas où il n'y a pas assez de données
        if response.status_code == 400:
            error_msg = response.json().get("error", "Erreur inconnue")
            await interaction.followup.send(f"⚠️ **Impossible d'analyser la méta** : {error_msg}")
            return

        response.raise_for_status()
        data = response.json()

        # 1. Traitement de l'image (Base64 -> Fichier Discord)
        image_b64 = data.get("image_base64")
        if not image_b64:
            await interaction.followup.send("❌ Erreur : Le backend n'a pas renvoyé d'image.")
            return

        image_bytes = base64.b64decode(image_b64)
        # On utilise io.BytesIO pour créer un fichier en mémoire
        file = discord.File(io.BytesIO(image_bytes), filename="meta_shap.png")

        # 2. Création de l'Embed
        embed = discord.Embed(
            title=f"🧠 Analyse Meta IA - {role.name}",
            description=(
                f"Voici ce que l'algorithme **XGBoost** détecte comme facteurs clés de victoire pour le rôle **{role.name}**.\n"
                "Les points **rouges** à **droite** de la ligne centrale font gagner la partie."
            ),
            color=discord.Color.purple()
        )

        # On attache l'image à l'embed
        embed.set_image(url="attachment://meta_shap.png")

        # 3. Ajout des Conseils Tactiques
        tips = data.get("tactical_tips", [])
        if tips:
            tips_text = ""
            for tip in tips:
                name = tip['name']
                imp = tip['importance_score']
                conseil = tip['tip']

                # Formatage joli
                tips_text += f"🔹 **{name}** (Impact: `{imp:.2f}`)\n   👉 *{conseil}*\n\n"

            embed.add_field(name="💡 Conseils Tactiques",
                            value=tips_text, inline=False)

        embed.set_footer(
            text="Généré par XGBoost + SHAP sur l'historique complet.")

        # Envoi de la réponse avec le fichier
        await interaction.followup.send(embed=embed, file=file)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send(f"❌ Erreur de connexion au backend : {e}")
    except Exception as e:
        await interaction.followup.send(f"❌ Une erreur interne est survenue : {e}")


@bot.tree.command(name="analyse", description="Analyse IA détaillée : Pourquoi tu gagnes (ou perds) ?")
@app_commands.describe(
    joueur="Le Riot ID complet (ex: MonPseudo#EUW)",
    role="Le rôle joué (Top, Jungle, Mid, ADC, Support)"
)
@app_commands.choices(role=[
    app_commands.Choice(name="Toplane", value="TOP"),
    app_commands.Choice(name="Jungle", value="JUNGLE"),
    app_commands.Choice(name="Midlane", value="MIDDLE"),
    app_commands.Choice(name="ADC (Bot)", value="BOTTOM"),
    app_commands.Choice(name="Support", value="UTILITY"),
])
async def analyse(interaction: discord.Interaction, joueur: str, role: app_commands.Choice[str]):
    """Demande une analyse SHAP personnalisée au backend."""
    await interaction.response.defer(thinking=True)

    selected_role = role.value

    # Validation basique du Riot ID (doit contenir #)
    if '#' not in joueur:
        await interaction.followup.send("❌ Format invalide. Le Riot ID doit contenir le tag (ex: `Pseudo#EUW`).")
        return

    try:
        # Appel à la route backend /personal_meta
        params = {'riot_id': joueur, 'role': selected_role}
        response = requests.get(f"{BACKEND_URL}/personal_meta", params=params)

        # Gestion des erreurs HTTP (400, 404, 500)
        if response.status_code != 200:
            error_msg = response.json().get("error", "Erreur inconnue du serveur.")
            await interaction.followup.send(f"⚠️ **Impossible de générer l'analyse** : {error_msg}")
            return

        data = response.json()
        image_b64 = data.get("image_base64")
        tips = data.get("text_analysis", [])

        if not image_b64:
            await interaction.followup.send("❌ Erreur : Le backend n'a pas renvoyé d'image.")
            return

        # Décodage de l'image
        image_bytes = base64.b64decode(image_b64)
        file = discord.File(io.BytesIO(image_bytes),
                            filename="analysis_shap.png")

        # Création de l'Embed
        embed = discord.Embed(
            title=f"🧠 Analyse IA - {joueur} ({role.name})",
            description=(
                "Ce graphique compare tes performances à l'**Optimal Théorique** calculé par l'IA.\n"
                "• **Rouge** 🟥 : Stats qui augmentent tes chances de victoire.\n"
                "• **Bleu** 🟦 : Stats qui te tirent vers le bas."
            ),
            color=discord.Color.brand_green()
        )

        embed.set_image(url="attachment://analysis_shap.png")

        # Ajout des conseils textuels
        if tips:
            tips_formatted = "\n\n".join(tips)
            embed.add_field(name="💡 Conclusions de l'IA",
                            value=tips_formatted, inline=False)

        embed.set_footer(
            text="Généré via XGBoost + SHAP (Méthode Scientifique)")

        await interaction.followup.send(embed=embed, file=file)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send(f"❌ Erreur de connexion au backend : {e}")
    except Exception as e:
        await interaction.followup.send(f"❌ Une erreur interne est survenue : {e}")

# Run the bot
if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Erreur: Le token du bot Discord n'est pas défini dans le fichier .env")
