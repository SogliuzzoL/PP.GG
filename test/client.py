import base64
import datetime
import json
import os
import time

import requests
from dotenv import dotenv_values

# Mapping des rôles pour un affichage plus clair
ROLE_MAPPING = {
    "1": "TOP",
    "2": "JUNGLE",
    "3": "MIDDLE",
    "4": "BOTTOM",
    "5": "UTILITY",
}

def get_lcu_lockfile_info():
    lockfile_path = None
    if os.name == 'nt':  # Windows
        lockfile_path = r"C:\Riot Games\League of Legends\lockfile"
    else:  # Mac/Linux
        lockfile_path = os.path.expanduser("~/Library/Application Support/Riot Games/League of Legends/lockfile")
        if not os.path.exists(lockfile_path):
            lockfile_path = os.path.expanduser("~/.config/Riot Games/League of Legends/lockfile")
    if not os.path.exists(lockfile_path):
        raise FileNotFoundError("Lockfile not found. Make sure League of Legends is running.")
    with open(lockfile_path, 'r') as f:
        lockfile = f.read().strip().split(':')
    port = lockfile[2]
    password = lockfile[3]
    return port, password

def get_eog_stats(port, password):
    url = f"https://127.0.0.1:{port}/lol-end-of-game/v1/eog-stats-block"
    auth = "riot:" + password
    headers = {
        "Authorization": "Basic " + base64.b64encode(auth.encode()).decode(),
    }
    try:
        response = requests.get(url, headers=headers, verify=False)
        if response.status_code == 200:
            return response.json()
        else:
            return None
    except Exception as e:
        print(f"Error: {e}")
        return None

def ask_for_role(player_name, player_tag):
    print(f"\nQuel est le rôle de {player_name}#{player_tag} ?")
    for key, role in ROLE_MAPPING.items():
        print(f"{key}. {role}")
    while True:
        choice = input("Entrez le numéro du rôle (1-5) : ").strip()
        if choice in ROLE_MAPPING:
            return ROLE_MAPPING[choice]
        else:
            print("Choix invalide. Veuillez entrer un numéro entre 1 et 5.")

def send_to_backend(match_data, config):
    url = f"{config['backend_url']}/add_match"
    try:
        response = requests.post(url, json=match_data)
        response.raise_for_status()
        print(f"Match envoyé au backend avec succès : {response.json()}")
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de l'envoi au backend : {e}")
        print(f"Réponse du serveur : {e.response.text if hasattr(e, 'response') else 'Pas de réponse'}")

def main():
    try:
        config = dotenv_values(".env")
        if not config or 'backend_url' not in config:
            raise ValueError("Le fichier .env est manquant ou la clé 'backend_url' n'est pas définie.")
        port, password = get_lcu_lockfile_info()
        print(f"En attente des stats de fin de partie (port {port})...")
        while True:
            stats = get_eog_stats(port, password)
            if stats:
                print("\nStats de fin de partie détectées !")
                for team in stats["teams"]:
                    for player in team["players"]:
                        if player["detectedTeamPosition"] == "":
                            role = ask_for_role(player["riotIdGameName"], player["riotIdTagLine"])
                            player["detectedTeamPosition"] = role
                # Sauvegarde locale des stats
                filename = f"data/eog_stats_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
                with open(filename, "w") as f:
                    json.dump(stats, f, indent=4)
                print(f"\nLes stats ont été sauvegardées dans {filename}.")
                # Envoi au backend
                send_to_backend(stats, config)
                break
            time.sleep(5)  # Poll every 5 seconds
    except Exception as e:
        print(f"Une erreur est survenue : {e}")

if __name__ == "__main__":
    main()
