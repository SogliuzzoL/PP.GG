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
        """Creates an embed for the current page of players."""
        embed = discord.Embed(
            title=f"Top Players - Page {self.current_offset // self.limit + 1}", color=discord.Color.blue())
        if not players_data:
            embed.description = "Il n'y a plus de joueurs à afficher."
        else:
            for i, player in enumerate(players_data, start=1+self.current_offset):
                riot_id = player.get('riot_id', 'Unknown#')
                game_name, tag_line = riot_id.split(
                    '#', 1) if '#' in riot_id else (riot_id, '')

                embed.add_field(
                    name=f"#{i} - {game_name}#{tag_line}",
                    value=f"μ={player.get('mu', 0):.2f} σ={player.get('sigma', 0):.2f}",
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
            value=f"**μ (Niveau)**: `{data.get('mu', 0):.2f}`\n**σ (Confiance)**: `{data.get('sigma', 0):.2f}`",
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
                f"**1.** {top_champions[0]['name']} ({top_champions[0]['count']} p.)"
            ]
            if len(top_champions) > 1:
                champ_list.append(
                    f"**2.** {top_champions[1]['name']} ({top_champions[1]['count']} p.)")
            if len(top_champions) > 2:
                champ_list.append(
                    f"**3.** {top_champions[2]['name']} ({top_champions[2]['count']} p.)")

            embed.add_field(
                name="🏆 Top Champions",
                value="\n".join(champ_list),
                inline=True
            )
        else:
            embed.add_field(name="🏆 Top Champions",
                            value="Aucun match joué", inline=True)

        # 3. Séparateur pleine largeur
        embed.add_field(name="\u200b", value="\u200b", inline=False)

        # 4. Section des moyennes (avec formatage amélioré)
        role_stats = data.get('role_specific_avg_stats', {})

        if role_stats:
            stats_list = []
            # Dictionnaire pour de plus jolis noms
            pretty_names = {
                "kda": "KDA", "kill_participation": "KP%", "cs_per_min": "CS/min",
                "gold_per_min": "Gold/min", "damage_dealt_per_min": "Dégâts/min",
                "vision_score_per_min": "Vision/min", "cc_score_per_min": "CC/min",
                "healing_on_teammates_per_min": "Heal(Alliés)/min",
                "shields_on_teammates_per_min": "Shield(Alliés)/min",
                "effective_tanking_per_min": "Tanking/min"
            }

            for stat_name, stat_value in role_stats.items():
                display_name = pretty_names.get(
                    stat_name, stat_name.replace('_', ' ').title())

                # 5. Formatage des chiffres (arrondis, %, etc.)
                if "kda" in stat_name:
                    value = f"{stat_value:.2f}"
                elif "participation" in stat_name:
                    value = f"{stat_value:.1f}%"
                elif "damage_dealt" in stat_name or "tanking" in stat_name:
                    # Pas de décimale pour les gros chiffres
                    value = f"{stat_value:.0f}"
                else:
                    value = f"{stat_value:.1f}"  # 1 décimale pour le reste

                stats_list.append(f"**{display_name}**: `{value}`")

            if stats_list:
                title = f"📊 Moyennes (Rôle: {data.get('main_role')})"

                # Divise en deux colonnes si + de 3 stats
                if len(stats_list) > 3:
                    mid_point = (len(stats_list) + 1) // 2
                    col1 = "\n".join(stats_list[:mid_point])
                    col2 = "\n".join(stats_list[mid_point:])

                    embed.add_field(name=title, value=col1, inline=True)
                    embed.add_field(name="\u200b", value=col2,
                                    inline=True)  # Nom invisible
                else:
                    embed.add_field(name=title, value="\n".join(
                        stats_list), inline=False)

        embed.set_footer(
            text="Statistiques basées sur l'historique de toutes les parties PP.GG")

        await interaction.followup.send(embed=embed)

    except requests.exceptions.RequestException as e:
        await interaction.followup.send(f"Erreur lors de la connexion au backend : {e}")
    except Exception as e:
        await interaction.followup.send(f"Une erreur inattendue est survenue : {e}")


# Run the bot
if __name__ == "__main__":
    if TOKEN:
        bot.run(TOKEN)
    else:
        print("Erreur: Le token du bot Discord n'est pas défini dans le fichier .env")
