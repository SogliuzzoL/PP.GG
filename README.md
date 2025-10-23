# PP.GG - Suivi de Performance pour League of Legends

PP.GG est un outil conçu pour suivre et évaluer le niveau de jeu (MMR) des joueurs dans les parties personnalisées de League of Legends. Il se compose d'un client de bureau, d'un serveur backend pour les calculs, et d'un bot Discord pour l'interaction avec les utilisateurs.

## Fonctionnalités

*   **Client de bureau** : Une application qui tourne en arrière-plan, détecte la fin d'une partie de League of Legends et récupère les statistiques.
*   **Envoi automatique** : Les statistiques de fin de partie sont automatiquement envoyées à un serveur backend pour analyse.
*   **Calcul de MMR** : Le backend utilise un système de classement (similaire à TrueSkill/Glicko, basé sur les valeurs `μ` et `σ`) pour mettre à jour le niveau de chaque joueur après une partie.
*   **API REST** : Le serveur expose des points d'accès pour ajouter des matchs, consulter le classement des meilleurs joueurs et voir les poids de performance.
*   **Bot Discord interactif** : Un bot Discord permet aux utilisateurs d'interagir avec le système :
    *   `/top` : Affiche le classement des meilleurs joueurs avec une pagination interactive.
    *   `/weights` : Affiche les poids actuels utilisés pour le calcul de la performance.
*   **Notifications Discord** : Après chaque partie, un résumé du match et la mise à jour du classement des joueurs sont publiés sur un serveur Discord via un webhook.
*   **Stockage local** : Les données des parties sont sauvegardées localement avant d'être envoyées, garantissant qu'aucune donnée n'est perdue en cas de problème de connexion.

## Architecture

1.  **Client (`client/client.py`)** :
    *   Application `Tkinter` qui s'exécute sur le PC d'un utilisateur.
    *   Elle surveille le "lockfile" du client League of Legends pour détecter quand une partie est en cours.
    *   À la fin de la partie, elle contacte l'API locale du client LoL pour obtenir les statistiques du match.
    *   Les statistiques sont sauvegardées dans le dossier `pending_uploads/`.
    *   Le client tente ensuite d'envoyer ces données au serveur backend. Si l'envoi réussit, le fichier est déplacé dans `sent_uploads/`.

2.  **Backend (`backend/main.py`)** :
    *   Serveur `Flask` qui écoute les requêtes du client et du bot.
    *   **`/add_match`** : Reçoit les données d'un match, met à jour le MMR des joueurs dans la base de données SQLite (`db.sqlite3`) et envoie une notification sur Discord.
    *   **`/top_players`** : Renvoie une liste des joueurs les mieux classés.
    *   **`/get_weights`** : Renvoie les poids utilisés pour le calcul de la performance.

3.  **Bot Discord (`bot/main.py`)** :
    *   Un bot basé sur `discord.py` qui répond aux commandes slash des utilisateurs.
    *   Il communique avec le backend via l'API REST pour récupérer les informations demandées (`/top_players`, `/get_weights`).
    *   Permet une consultation facile et rapide des données sans quitter Discord.

## Technologies utilisées

*   **Langage** : Python
*   **Backend** : Flask
*   **Client** : Tkinter
*   **Bot** : discord.py
*   **Base de données** : SQLite
*   **Bibliothèques principales** : `requests`, `numpy`, `python-dotenv`

## Installation et Lancement

1.  **Cloner le dépôt**
    ```bash
    git clone <url-du-repo>
    cd PP.GG
    ```

2.  **Créer un environnement virtuel et installer les dépendances**
    ```bash
    python -m venv venv
    source venv/bin/activate  # Sur Windows: venv\Scripts\activate
    pip install -r requirements.txt
    ```

3.  **Configurer les variables d'environnement**
    Créez un fichier `.env` à la racine du projet avec le contenu suivant :
    ```env
    # Chemin vers la base de données
    db_path=data/db.sqlite3

    # Configuration du backend
    backend_url=http://127.0.0.1:5000

    # URL du Webhook Discord pour les notifications de match
    discord_webhook_url=https://discord.com/api/webhooks/your/webhook

    # Token du bot Discord
    discord_token=your_discord_bot_token
    ```

4.  **Lancer le serveur backend**
    ```bash
    python backend/main.py
    ```
    Le serveur sera accessible à l'adresse `http://localhost:5000`.

5.  **Lancer le bot Discord**
    Dans un nouveau terminal :
    ```bash
    python bot/main.py
    ```

6.  **Lancer le client**
    Dans un autre terminal :
    ```bash
    python client/client.py
    ```
    Le client s'exécutera en arrière-plan et commencera à surveiller le client League of Legends.
