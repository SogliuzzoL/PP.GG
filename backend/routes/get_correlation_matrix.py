import os
import sqlite3

import matplotlib.pyplot as plt
import pandas as pd
import seaborn as sns
from flask import Request, jsonify, send_file

# Import de la fonction clé pour récupérer les données
from models.database import get_all_historical_data

# Désactiver l'avertissement de Matplotlib pour l'utilisation dans un thread
plt.switch_backend('Agg')

# Les rôles valides (pour la sécurité et la validation)
VALID_ROLES = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]


def generate_matrix_image(role: str, db_path: str) -> tuple[str, str | None]:
    """
    Génère l'image de la matrice de corrélation pour un rôle.
    Utilise les données de la base de données.
    Retourne (chemin_du_fichier, message_erreur | None).
    """

    # 1. Définir le chemin de sortie (à la racine du projet)
    file_name = f"correlation_matrix_{role}.png"
    # Le chemin est construit depuis ce fichier (backend/routes/)
    # en remontant de deux niveaux (..) pour atteindre la racine du projet.
    file_path = os.path.abspath(os.path.join(
        os.path.dirname(__file__), '..', '..', file_name))

    conn = None
    try:
        # 2. Obtenir les données historiques depuis la BDD
        conn = sqlite3.connect(db_path)
        # get_all_historical_data calcule déjà les métriques _per_min, kda, etc.
        all_data_df = get_all_historical_data(conn)
    except Exception as e:
        print(
            f"Erreur lors de la connexion BDD ou get_all_historical_data: {e}")
        return None, f"Database error: {e}"
    finally:
        if conn:
            conn.close()

    if all_data_df.empty:
        print("Pas de données historiques trouvées pour générer la matrice.")
        return None, "No historical data to generate matrix."

    # 3. Filtrer les données pour le rôle
    role_df = all_data_df[all_data_df['role'] == role]
    if len(role_df) < 2:
        print(
            f"Pas assez de données pour le rôle {role} (besoin d'au moins 2).")
        return None, f"Not enough data for role: {role} (need at least 2 entries)."

    # 4. Préparer le DataFrame pour la corrélation
    numeric_role_df = role_df.select_dtypes(include=['number'])

    # Exclure les colonnes non pertinentes pour la corrélation
    cols_to_drop = [col for col in [
        'match_id', 'team_damage_percentage'] if col in numeric_role_df.columns]
    if cols_to_drop:
        numeric_role_df = numeric_role_df.drop(columns=cols_to_drop)

    # Calculer la matrice
    correlation_matrix = numeric_role_df.corr()

    # 5. Générer le graphique
    try:
        plt.figure(figsize=(14, 12))
        sns.heatmap(correlation_matrix, annot=True,
                    cmap='coolwarm', fmt=".2f", linewidths=.5, vmin=-1, vmax=1)
        plt.title(f'Matrice de Corrélation (Live) - Rôle : {role}')

        # 6. Sauvegarder l'image
        plt.savefig(file_path, bbox_inches='tight')
        plt.close()  # Important pour libérer la mémoire dans un serveur

        print(f"Matrice régénérée : {file_path}")
        return file_path, None

    except Exception as e:
        print(f"Erreur lors de la génération du PNG: {e}")
        # S'assurer de fermer la figure en cas d'erreur
        if plt.gcf().get_axes():
            plt.close()
        return None, f"Plotting error: {e}"


def get_correlation_matrix(request: Request, role: str, config: dict):
    """
    Régénère et envoie l'image de la matrice de corrélation.
    """
    role_upper = role.upper()

    # 1. Valider le rôle
    if role_upper not in VALID_ROLES:
        return jsonify({"error": "Invalid role specified"}), 400

    # 2. Récupérer le db_path depuis la config
    db_path = config.get("db_path")
    if not db_path:
        return jsonify({"error": "db_path not configured in .env"}), 500

    # 3. Appeler la fonction de génération
    file_path, error = generate_matrix_image(role_upper, db_path)

    if error:
        # Une erreur est survenue pendant la génération
        return jsonify({"error": error}), 500

    # 4. Envoyer le fichier nouvellement créé
    try:
        # Mettre max_age=0 force le navigateur à ne pas utiliser de cache
        return send_file(file_path, mimetype='image/png', max_age=0)
    except Exception as e:
        print(f"Erreur lors de l'envoi du fichier {file_path}: {e}")
        return jsonify({"error": f"Could not send file: {e}"}), 500
