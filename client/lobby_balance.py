import base64
import json
import os

import requests
import urllib3
from dotenv import dotenv_values

# Désactiver les warnings SSL pour le client local
urllib3.disable_warnings(urllib3.exceptions.InsecureRequestWarning)


def get_lcu_lockfile_info():
    """Récupère le port et le mot de passe du client LoL via le lockfile."""
    lockfile_path = None
    if os.name == 'nt':  # Windows
        lockfile_path = r"C:\Riot Games\League of Legends\lockfile"
    else:  # Mac/Linux
        lockfile_path = os.path.expanduser(
            "~/Library/Application Support/Riot Games/League of Legends/lockfile")
        if not os.path.exists(lockfile_path):
            lockfile_path = os.path.expanduser(
                "~/.config/Riot Games/League of Legends/lockfile")

    if not os.path.exists(lockfile_path):
        print("❌ Lockfile introuvable. Assure-toi que le client LoL est ouvert.")
        return None, None

    with open(lockfile_path, 'r') as f:
        data = f.read().strip().split(':')
    return data[2], data[3]  # Port, Password


def get_headers(password):
    auth = "riot:" + password
    return {
        "Authorization": "Basic " + base64.b64encode(auth.encode()).decode()
    }


def get_lobby_players(port, password):
    """Récupère les joueurs du lobby actuel."""
    base_url = f"https://127.0.0.1:{port}"
    headers = get_headers(password)

    try:
        # 1. Récupérer les membres du lobby
        response = requests.get(
            f"{base_url}/lol-lobby/v2/lobby", headers=headers, verify=False)

        if response.status_code == 404:
            print("❌ Tu n'es pas dans un lobby !")
            return []

        lobby_data = response.json()
        members = lobby_data.get('members', [])

        player_riot_ids = []

        print(f"🔍 Analyse du lobby ({len(members)} joueurs détectés)...")

        # 2. Pour chaque membre, récupérer son Riot ID (GameName + TagLine)
        for member in members:
            summoner_id = member.get('summonerId')

            # Appel API pour avoir les détails du summoner
            sum_resp = requests.get(
                f"{base_url}/lol-summoner/v1/summoners/{summoner_id}", headers=headers, verify=False)

            if sum_resp.status_code == 200:
                s_data = sum_resp.json()
                game_name = s_data.get('gameName')
                tag_line = s_data.get('tagLine')
                full_id = f"{game_name}#{tag_line}"
                player_riot_ids.append(full_id)
            else:
                print(
                    f"⚠️ Erreur récupération infos pour summoner {summoner_id}")

        return player_riot_ids

    except Exception as e:
        print(f"❌ Erreur lors de la communication avec le client : {e}")
        return []


def balance_lobby():
    # Charger la config (URL du backend)
    config = dotenv_values(".env")
    backend_url = config.get('backend_url', 'http://localhost:5000')

    # 1. Connexion au client LoL
    port, password = get_lcu_lockfile_info()
    if not port:
        return

    # 2. Récupération des joueurs
    players = get_lobby_players(port, password)

    if not players:
        return

    # --- ÉTAPE DE FILTRAGE ---
    print("\n📋 Liste des joueurs :")
    for i, p in enumerate(players):
        print(f"   [{i+1}] {p}")

    print("\n👉 S'il y a des spectateurs ou des joueurs à exclure :")
    to_remove = input(
        "   Entre leurs numéros séparés par un espace (ex: '1 11') ou tape Entrée : ")

    if to_remove.strip():
        try:
            indices_to_remove = [int(x) - 1 for x in to_remove.split()]
            # On reconstruit la liste en excluant les index choisis
            filtered_players = [p for idx, p in enumerate(
                players) if idx not in indices_to_remove]

            print(
                f"✅ {len(players) - len(filtered_players)} joueur(s) retiré(s). Reste : {len(filtered_players)}")
            players = filtered_players
        except ValueError:
            print("❌ Erreur de saisie. Aucun joueur retiré.")

    if len(players) < 2:
        print("⚠️ Pas assez de joueurs pour équilibrer (min 2).")
        return

    # 3. Envoi au Backend pour équilibrage
    print("\n⚖️  Demande d'équilibrage au backend...")
    try:
        resp = requests.post(
            f"{backend_url}/balance_teams", json={'players': players})

        if resp.status_code == 200:
            data = resp.json()
            team1 = data['team1']
            team2 = data['team2']
            diff = data['rating_diff']

            print("\n" + "="*40)
            print(f"🏆 ÉQUIPES GÉNÉRÉES (Écart: {diff:.2f})")
            print("="*40)

            print(f"\n🔵 ÉQUIPE 1 (Moy: {data['avg_team1']:.0f})")
            for p in team1:
                print(f"   - {p['riot_id']} ({p['rating']:.0f})")

            print(f"\n🔴 ÉQUIPE 2 (Moy: {data['avg_team2']:.0f})")
            for p in team2:
                print(f"   - {p['riot_id']} ({p['rating']:.0f})")
            print("="*40)
            print("\n📨 Webhook envoyé à Discord !")
        else:
            print(f"❌ Erreur backend : {resp.text}")

    except requests.exceptions.ConnectionError:
        print(f"❌ Impossible de contacter le backend sur {backend_url}")


if __name__ == "__main__":
    balance_lobby()
    input("\nAppuie sur Entrée pour quitter...")
