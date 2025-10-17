import base64
import datetime
import json
import os
import time
import tkinter as tk
from threading import Event, Thread
from tkinter import messagebox, ttk

import requests
from dotenv import dotenv_values

# Mapping des rôles
ROLE_MAPPING = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]

class LockfileWaitWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("Attente du Lockfile")
        self.root.geometry("300x120")
        ttk.Label(root, text="En attente du lockfile de League of Legends...", wraplength=280).pack(pady=10)
        self.cancel_button = ttk.Button(root, text="Annuler", command=self.on_close)
        self.cancel_button.pack(pady=10)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.closed = False

    def on_close(self):
        self.closed = True
        self.root.destroy()

class EndGameWaitWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("Attente de la fin de partie")
        self.root.geometry("300x120")
        ttk.Label(root, text="En attente des stats de fin de partie...", wraplength=280).pack(pady=10)
        self.cancel_button = ttk.Button(root, text="Annuler", command=self.on_close)
        self.cancel_button.pack(pady=10)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.closed = False

    def on_close(self):
        self.closed = True
        self.root.destroy()

class RoleSelectorApp:
    def __init__(self, root, players):
        self.root = root
        self.players = players
        self.root.title("Sélection des rôles")
        self.root.geometry("500x400")
        self.role_vars = {}
        self.canceled = False

        ttk.Label(root, text="Sélectionnez le rôle pour chaque joueur :", font=('Helvetica', 12, 'bold')).pack(pady=10)

        for player in self.players:
            frame = ttk.Frame(root)
            frame.pack(fill='x', pady=2)
            ttk.Label(frame, text=f"{player['riotIdGameName']}#{player['riotIdTagLine']}: ", width=20).pack(side='left')
            var = tk.StringVar(value=player.get("detectedTeamPosition", ""))
            self.role_vars[player['puuid']] = var
            ttk.OptionMenu(frame, var, var.get(), *ROLE_MAPPING).pack(side='left', padx=5)

        button_frame = ttk.Frame(root)
        button_frame.pack(pady=20)
        ttk.Button(button_frame, text="Valider", command=self.on_validate).pack(side='left', padx=10)
        ttk.Button(button_frame, text="Annuler", command=self.on_close).pack(side='left', padx=10)

    def on_validate(self):
        for puuid, var in self.role_vars.items():
            for player in self.players:
                if player['puuid'] == puuid:
                    player['detectedTeamPosition'] = var.get()
        self.root.quit()

    def on_close(self):
        self.canceled = True
        self.root.quit()

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

def send_to_backend(match_data, config):
    url = f"{config['backend_url']}/add_match"
    try:
        response = requests.post(url, json=match_data)
        response.raise_for_status()
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de l'envoi au backend : {e}")
        return None

def wait_for_lockfile(root, stop_event):
    while not stop_event.is_set():
        try:
            port, password = get_lcu_lockfile_info()
            root.root.after(0, root.root.destroy)
            return port, password
        except Exception as e:
            print(f"Erreur lors de la recherche du lockfile : {e}")
            time.sleep(2)
    return None, None

def wait_for_eog_stats(root, port, password, stop_event):
    while not stop_event.is_set():
        stats = get_eog_stats(port, password)
        if stats:
            root.root.after(0, root.root.destroy)
            return stats
        time.sleep(5)
    return None

def main():
    try:
        config = dotenv_values(".env")
        if not config or 'backend_url' not in config:
            messagebox.showerror("Erreur", "Le fichier .env est manquant ou la clé 'backend_url' n'est pas définie.")
            return

        # Fenêtre d'attente du lockfile
        lockfile_root = tk.Tk()
        lockfile_window = LockfileWaitWindow(lockfile_root)
        stop_event = Event()
        thread = Thread(target=wait_for_lockfile, args=(lockfile_window, stop_event))
        thread.start()
        lockfile_root.mainloop()
        if lockfile_window.closed:
            stop_event.set()
            return

        port, password = wait_for_lockfile(lockfile_window, stop_event)

        # Fenêtre d'attente de la fin de partie
        eog_root = tk.Tk()
        eog_window = EndGameWaitWindow(eog_root)
        thread = Thread(target=wait_for_eog_stats, args=(eog_window, port, password, stop_event))
        thread.start()
        eog_root.mainloop()
        if eog_window.closed:
            stop_event.set()
            return

        stats = wait_for_eog_stats(eog_window, port, password, stop_event)

        # Fenêtre de sélection des rôles
        players = []
        for team in stats["teams"]:
            players.extend(team["players"])

        role_root = tk.Tk()
        app = RoleSelectorApp(role_root, players)
        role_root.mainloop()

        if app.canceled:
            return

        # Sauvegarde locale des stats
        filename = f"eog_stats_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w") as f:
            json.dump(stats, f, indent=4)
        print(f"\nLes stats ont été sauvegardées dans {filename}.")

        # Envoi au backend
        result = send_to_backend(stats, config)
        if result:
            messagebox.showinfo("Succès", f"Match envoyé au backend avec succès : {result}")
        else:
            messagebox.showerror("Erreur", "L'envoi au backend a échoué.")

    except Exception as e:
        messagebox.showerror("Erreur", f"Une erreur est survenue : {e}")

if __name__ == "__main__":
    main()
