import os
import sqlite3
import sys

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import shap
import xgboost as xgb

current_dir = os.path.dirname(os.path.abspath(__file__))
backend_dir = os.path.abspath(os.path.join(current_dir, '..'))
sys.path.append(backend_dir)


# Configuration
DB_PATH = "data/db.sqlite3"
OUTPUT_DIR = os.path.join(current_dir, 'output_visuals')
os.makedirs(OUTPUT_DIR, exist_ok=True)

ROLE_COLORS = {
    "TOP": "#e74c3c", "JUNGLE": "#2ecc71", "MIDDLE": "#3498db",
    "BOTTOM": "#9b59b6", "UTILITY": "#f1c40f"
}


def analyze_role(role, df):
    print(f"\n--- Analyse XGBoost pour {role} ---")

    # 1. Préparation des données
    role_df = df[df['role'] == role].copy()

    if len(role_df) < 20:
        print(
            f"Pas assez de données pour {role} ({len(role_df)} parties). Skipping.")
        return

    # Nettoyage : On garde uniquement les colonnes numériques (features) et la cible (win)
    # On retire les IDs et le rôle
    drop_cols = ['match_id', 'role', 'riot_id', 'champion',
                 'team', 'position']  # Ajoute ici les colonnes non-stats
    features_df = role_df.drop(
        columns=[c for c in drop_cols if c in role_df.columns])

    X = features_df.drop(columns=['win'])
    y = features_df['win']

    # 2. Entraînement XGBoost
    # On utilise un modèle simple mais robuste
    model = xgb.XGBClassifier(
        n_estimators=100,
        max_depth=3,
        learning_rate=0.1,
        use_label_encoder=False,
        eval_metric='logloss'
    )
    model.fit(X, y)

    # 3. Visuel 1 : Feature Importance (Poids global)
    plt.figure(figsize=(10, 6))
    sorted_idx = model.feature_importances_.argsort()
    plt.barh(X.columns[sorted_idx], model.feature_importances_[
             sorted_idx], color=ROLE_COLORS.get(role, 'gray'))
    plt.title(f"XGBoost Feature Importance - {role}")
    plt.xlabel("Impact relatif sur la victoire")

    save_path = os.path.join(OUTPUT_DIR, f"importance_{role}.png")
    plt.savefig(save_path, bbox_inches='tight')
    plt.close()
    print(f"Graphique d'importance sauvegardé : {save_path}")

    # 4. Visuel 2 : SHAP Summary Plot (Impact directionnel)
    # C'est le visuel le plus puissant pour comprendre le "Pourquoi"
    try:
        explainer = shap.Explainer(model, X)
        shap_values = explainer(X)

        plt.figure(figsize=(10, 6))
        plt.title(f"SHAP Summary - Comment gagner en {role} ?")
        # Le plot SHAP est complexe à sauver proprement avec matplotlib, on fait simple :
        shap.summary_plot(shap_values, X, show=False)

        shap_save_path = os.path.join(OUTPUT_DIR, f"shap_{role}.png")
        plt.savefig(shap_save_path, bbox_inches='tight')
        plt.close()
        print(f"Graphique SHAP sauvegardé : {shap_save_path}")

    except Exception as e:
        print(f"Erreur lors de la génération SHAP pour {role}: {e}")


def main():
    # Connexion BDD
    if not os.path.exists(DB_PATH):
        print(f"Erreur: Base de données non trouvée à {DB_PATH}")
        return

    conn = sqlite3.connect(DB_PATH)
    try:
        print("Chargement de l'historique complet...")
        from models.database import get_all_historical_data
        df = get_all_historical_data(conn)
    finally:
        conn.close()

    if df.empty:
        print("Aucune donnée trouvée.")
        return

    # Lancer l'analyse pour chaque rôle
    for role in ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]:
        analyze_role(role, df)


if __name__ == "__main__":
    main()
