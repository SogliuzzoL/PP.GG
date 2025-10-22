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

# --- Constantes pour les dossiers de sauvegarde ---
PENDING_DIR = "pending_uploads"
SENT_DIR = "sent_uploads"

# Mapping des rôles
ROLE_MAPPING = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]


class LockfileWaitWindow:
    def __init__(self, root):
        self.root = root
        self.root.title("Attente du Lockfile")
        self.root.geometry("300x120")
        ttk.Label(root, text="En attente du lockfile de League of Legends...",
                  wraplength=280).pack(pady=10)
        self.cancel_button = ttk.Button(
            root, text="Annuler", command=self.on_close)
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
        ttk.Label(root, text="En attente des stats de fin de partie...",
                  wraplength=280).pack(pady=10)
        self.cancel_button = ttk.Button(
            root, text="Annuler", command=self.on_close)
        self.cancel_button.pack(pady=10)
        self.root.protocol("WM_DELETE_WINDOW", self.on_close)
        self.closed = False

    def on_close(self):
        self.closed = True
        self.root.destroy()


class RoleSelectorApp:
    def __init__(self, root, teams):
        self.root = root
        self.teams = teams
        self.root.title("Sélection des rôles")
        self.root.geometry("700x400")
        self.role_vars = {}
        self.canceled = False

        ttk.Label(root, text="Sélectionnez le rôle pour chaque joueur :",
                  font=('Helvetica', 12, 'bold')).pack(pady=10)

        # Frame principal pour contenir les deux colonnes
        main_frame = ttk.Frame(root)
        main_frame.pack(fill='both', expand=True, padx=10, pady=5)

        # Labels pour les équipes (généralement 100=Bleu, 200=Rouge)
        team_labels = ["Équipe 1 (Bleue)", "Équipe 2 (Rouge)"]

        for i, team in enumerate(self.teams):
            # Utiliser un LabelFrame pour chaque colonne d'équipe
            team_label = team_labels[i] if i < len(
                team_labels) else f"Équipe {i + 1}"
            team_frame = ttk.LabelFrame(main_frame, text=team_label)
            team_frame.pack(side='left', fill='both',
                            expand=True, padx=10, pady=5)

            # Ajouter les joueurs à la frame de leur équipe
            for player in team["players"]:
                frame = ttk.Frame(team_frame)
                frame.pack(fill='x', pady=3, padx=5)

                label_text = f"{player['riotIdGameName']}#{player['riotIdTagLine']}: "
                ttk.Label(frame, text=label_text, width=28).pack(side='left')

                var = tk.StringVar(value=player.get(
                    "detectedTeamPosition", ""))
                self.role_vars[player['puuid']] = var

                # S'assurer qu'une valeur est affichée même si vide
                display_val = var.get() if var.get() else ROLE_MAPPING[0]

                ttk.OptionMenu(frame, var, display_val, *
                               ROLE_MAPPING).pack(side='left', padx=5, fill='x', expand=True)

        button_frame = ttk.Frame(root)
        button_frame.pack(pady=20)
        ttk.Button(button_frame, text="Valider",
                   command=self.on_validate).pack(side='left', padx=10)
        ttk.Button(button_frame, text="Annuler",
                   command=self.on_close).pack(side='left', padx=10)

    def on_validate(self):
        for puuid, var in self.role_vars.items():
            player_found = False
            for team in self.teams:
                for player in team["players"]:
                    if player['puuid'] == puuid:
                        player['detectedTeamPosition'] = var.get()
                        player_found = True
                        break
                if player_found:
                    break
        self.root.quit()

    def on_close(self):
        self.canceled = True
        self.root.quit()


def get_lcu_lockfile_info():
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
        raise FileNotFoundError(
            "Lockfile not found. Make sure League of Legends is running.")
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
        # verify=False pour ignorer les erreurs de certificat SSL (LCU utilise un cert auto-signé)
        response = requests.get(url, headers=headers,
                                verify=False, timeout=5)  # Ajout timeout
        if response.status_code == 200:
            return response.json()
        else:
            # Stats pas encore prêtes (404, etc.)
            return None
    except requests.exceptions.ConnectionError as e:
        # ERREUR CRITIQUE: Le client LCU est inaccessible (crash / fermé)
        print(
            f"ConnectionError dans get_eog_stats: {e}. Le client LCU est probablement fermé.")
        raise  # On propage l'erreur pour que le thread parent la gère
    except Exception as e:
        print(f"Erreur générique dans get_eog_stats: {e}")
        return None


def send_to_backend(match_data, config):
    url = f"{config['backend_url']}/add_match"
    try:
        response = requests.post(url, json=match_data,
                                 timeout=10)  # Ajout d'un timeout
        response.raise_for_status()  # Lève une exception pour les codes 4xx/5xx
        return response.json()
    except requests.exceptions.RequestException as e:
        print(f"Erreur lors de l'envoi au backend : {e}")
        return None


def wait_for_lockfile(root, stop_event, result_list):
    """Attend le lockfile et place (port, password) dans result_list."""
    while not stop_event.is_set():
        try:
            port, password = get_lcu_lockfile_info()
            # Le lockfile est trouvé, fermer la fenêtre d'attente
            root.root.after(0, root.root.destroy)
            result_list.append((port, password))  # Stocker le résultat
            return
        except Exception as e:
            print(f"Erreur lors de la recherche du lockfile : {e}")
            time.sleep(10)
    result_list.append(None)  # Si on sort à cause de stop_event


def wait_for_eog_stats(root, port, password, stop_event, result_list, last_processed_game_id):
    """
    Attend les stats EOG et place les stats (ou un message d'erreur) dans result_list.
    Ignore le match si son gameId est égal à last_processed_game_id.
    """
    while not stop_event.is_set():
        try:
            stats = get_eog_stats(port, password)
            if stats:
                current_game_id = stats.get('gameId')
                if current_game_id and current_game_id == last_processed_game_id:
                    # C'est le même match qu'on vient de traiter (probablement un échec d'envoi)
                    # On l'ignore et on attend 5 sec.
                    print(
                        f"Ignoré gameId {current_game_id} (déjà traité), en attente d'un nouveau match...")
                else:
                    # C'est un nouveau match, on le traite
                    print(f"Nouveau match trouvé : {current_game_id}")
                    root.root.after(0, root.root.destroy)
                    result_list.append(stats)  # Stocker le résultat
                    return
        except requests.exceptions.ConnectionError:
            # Le client a crashé !
            print(
                "Connexion LCU perdue (crash détecté). Retour à la recherche du lockfile.")
            root.root.after(0, root.root.destroy)
            result_list.append("CRASH_DETECTED")  # Signal de crash
            return
        except Exception as e:
            # Erreur inattendue dans la boucle
            print(f"Erreur inattendue dans la boucle wait_for_eog: {e}")

        time.sleep(5)
    result_list.append(None)  # Si on sort à cause de stop_event


def retry_pending_uploads(config):
    """
    Parcourt le dossier PENDING_DIR et tente d'envoyer chaque fichier .json
    au backend. En cas de succès, déplace le fichier vers SENT_DIR.
    """
    print("Tentative d'envoi des matchs en attente...")
    if not os.path.exists(PENDING_DIR):
        print("Le dossier 'pending' n'existe pas, rien à envoyer.")
        return

    pending_files = [f for f in os.listdir(PENDING_DIR) if f.endswith('.json')]
    if not pending_files:
        print("Aucun match en attente.")
        return

    success_count = 0
    fail_count = 0

    for filename in pending_files:
        pending_path = os.path.join(PENDING_DIR, filename)
        try:
            with open(pending_path, 'r') as f:
                stats = json.load(f)

            print(f"Envoi de {filename}...")
            result = send_to_backend(stats, config)

            if result:
                print(f"Succès pour {filename}.")
                sent_path = os.path.join(SENT_DIR, filename)
                os.rename(pending_path, sent_path)  # Déplace le fichier
                success_count += 1
            else:
                print(f"Échec pour {filename}, restera en attente.")
                fail_count += 1
        except Exception as e:
            print(f"Erreur lors du traitement de {filename}: {e}")
            fail_count += 1

    print(
        f"Retentative terminée. {success_count} match(s) envoyé(s), {fail_count} échec(s).")
    # On pourrait utiliser un messagebox, mais cela bloquerait le thread principal
    # au démarrage. Le log console est plus approprié ici.


def main():
    try:
        # Créer les dossiers pour les stats s'ils n'existent pas
        os.makedirs(PENDING_DIR, exist_ok=True)
        os.makedirs(SENT_DIR, exist_ok=True)

        # Charger la configuration
        config = dotenv_values(".env")
        if not config or 'backend_url' not in config:
            messagebox.showerror(
                "Erreur", "Le fichier .env est manquant ou la clé 'backend_url' n'est pas définie.")
            return

        # --- NOUVEAU: Lancer la retentative dans un thread ---
        # Cela évite de bloquer le démarrage de l'application pendant que
        # l'on tente d'envoyer les anciens matchs.
        retry_thread = Thread(target=retry_pending_uploads,
                              args=(config,), daemon=True)
        retry_thread.start()

        last_processed_game_id = None  # Mémorise le dernier gameId traité
        keep_running = True  # Drapeau pour contrôler les boucles principales

        # --- Boucle principale de l'application ---
        # Cette boucle permet à l'application de redémarrer son cycle
        # si le client LCU crashe et redémarre.
        while keep_running:
            # Fenêtre d'attente du lockfile
            lockfile_root = tk.Tk()
            lockfile_window = LockfileWaitWindow(lockfile_root)
            stop_event = Event()
            lockfile_result = []  # Liste pour stocker le résultat du thread

            # Le thread `wait_for_lockfile` s'arrêtera si stop_event est set (par ex. si on ferme la fenêtre)
            # Il détruira lui-même la fenêtre s'il trouve le lockfile
            thread = Thread(target=wait_for_lockfile,
                            args=(lockfile_window, stop_event, lockfile_result))
            thread.start()
            lockfile_root.mainloop()  # Bloque jusqu'à ce que la fenêtre soit détruite

            if lockfile_window.closed:
                print("Annulé par l'utilisateur (attente lockfile).")
                stop_event.set()
                keep_running = False  # Arrêter l'application
                continue  # Saute le reste de la boucle, la condition while arrêtera

            thread.join()  # Attendre la fin du thread

            if not lockfile_result or not lockfile_result[0]:
                print("N'a pas pu récupérer le lockfile, arrêt.")
                keep_running = False  # Arrêter l'application
                continue  # Saute le reste de la boucle

            port, password = lockfile_result[0]
            print(f"Lockfile trouvé. Port: {port}")

            # --- Boucle interne: Attente de parties ---
            # Tant que le client est ouvert (même port/mdp), on attend
            # de nouvelles fins de partie.
            while keep_running:
                # Fenêtre d'attente de la fin de partie
                eog_root = tk.Tk()
                eog_window = EndGameWaitWindow(eog_root)
                eog_result = []  # Liste pour stocker le résultat

                thread = Thread(target=wait_for_eog_stats, args=(
                    eog_window, port, password, stop_event, eog_result, last_processed_game_id))
                thread.start()
                eog_root.mainloop()  # Bloque jusqu'à ce que la fenêtre soit détruite

                # Si on a annulé la fenêtre "attente eog", on sort
                # de la boucle interne pour revenir à "attente lockfile".
                if eog_window.closed:
                    print("Annulé par l'utilisateur (attente EOG).")
                    keep_running = False  # Arrêter l'application
                    break

                thread.join()  # Attendre la fin du thread

                if not eog_result:
                    print("Sortie de l'attente EOG sans résultat.")
                    keep_running = False  # Arrêter l'application
                    break  # Retour à l'attente du lockfile

                stats = eog_result[0]

                if stats == "CRASH_DETECTED":
                    # Le client a crashé. Sortir de la boucle interne
                    # pour retourner à la recherche du lockfile.
                    print("Crash détecté, retour à la recherche du lockfile.")
                    break  # Sort de la boucle interne

                if not stats:
                    print("Impossible de récupérer les stats EOG.")
                    # On continue la boucle interne pour réessayer
                    time.sleep(5)
                    continue

                print("Stats de fin de partie trouvées.")
                # Fenêtre de sélection des rôles
                role_root = tk.Tk()
                app = RoleSelectorApp(role_root, stats["teams"])
                role_root.mainloop()

                if app.canceled:
                    print("Annulé par l'utilisateur (sélection des rôles).")
                    # L'utilisateur a annulé *cette partie*.
                    # On arrête le programme comme demandé.
                    print("Arrêt du programme.")
                    keep_running = False
                    break  # Quitte la boucle EOG

                # --- Logique de sauvegarde et d'envoi ---

                # Marquer ce gameId comme traité, qu'il réussisse ou échoue,
                # pour ne pas le re-traiter en boucle.
                try:
                    last_processed_game_id = stats['gameId']
                except KeyError:
                    print(
                        "Attention: 'gameId' non trouvé dans les stats. La détection de boucle pourrait échouer.")

                filename = f"eog_stats_{datetime.datetime.now().strftime('%Y%m%d_%H%M%S')}.json"

                # 1. Toujours sauvegarder dans 'pending'
                pending_path = os.path.join(PENDING_DIR, filename)
                try:
                    with open(pending_path, "w") as f:
                        json.dump(stats, f, indent=4)
                    print(
                        f"\nLes stats ont été sauvegardées dans {pending_path}.")
                except Exception as e:
                    messagebox.showerror(
                        "Erreur Sauvegarde", f"Impossible de sauvegarder les stats localement: {e}")
                    # On ne retourne pas, on continue pour attendre la prochaine partie
                    continue

                # 2. Essayer d'envoyer
                print("Envoi des stats au backend...")
                result = send_to_backend(stats, config)

                # 3. Gérer le résultat
                if result:
                    messagebox.showinfo(
                        "Succès", f"Match envoyé au backend avec succès : {result.get('message', 'OK')}")

                    # 4. Si succès, déplacer de 'pending' à 'sent'
                    try:
                        sent_path = os.path.join(SENT_DIR, filename)
                        os.rename(pending_path, sent_path)
                        print(f"Stats déplacées vers {sent_path}.")
                    except Exception as e:
                        print(
                            f"Erreur lors du déplacement du fichier vers 'sent': {e}")
                        messagebox.showwarning("Erreur Fichier",
                                               f"Envoi réussi, mais erreur lors du déplacement du fichier: {e}. "
                                               "Le fichier sera peut-être renvoyé au prochain démarrage.")
                else:
                    # 5. Si échec, informer l'utilisateur que le fichier reste en attente
                    messagebox.showerror("Erreur Réseau",
                                         "L'envoi au backend a échoué. "
                                         f"Le match est sauvegardé dans '{PENDING_DIR}' et sera renvoyé automatiquement au prochain lancement.")

                # Fin du traitement de la partie.
                # L'application va maintenant s'arrêter comme demandé.
                print("Match traité. Arrêt du programme.")
                keep_running = False  # Indique aux DEUX boucles de s'arrêter
                break  # Quitte la boucle EOG

            # Fin de la boucle EOG.
            # Si keep_running est False, la boucle Lockfile s'arrêtera aussi.

    except Exception as e:
        messagebox.showerror("Erreur Inattendue",
                             f"Une erreur critique est survenue : {e}")
    finally:
        print("Arrêt de l'application.")


if __name__ == "__main__":
    # Désactiver les avertissements SSL pour les requêtes vers l'API LCU
    requests.packages.urllib3.disable_warnings(
        requests.packages.urllib3.exceptions.InsecureRequestWarning
    )
    main()
