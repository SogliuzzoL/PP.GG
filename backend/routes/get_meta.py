import base64
import io
import sqlite3

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import shap
import xgboost as xgb
from dotenv import dotenv_values
from flask import jsonify, send_file
from models.database import get_all_historical_data
from utils.performance import XGBoostScorer

matplotlib.use('Agg')  # Important pour le serveur (pas de GUI)


config = dotenv_values(".env")

# Dictionnaire pour traduire les noms de variables en langage "Joueur"
READABLE_NAMES = {
    "kda": "KDA",
    "kill_participation": "Partic. aux Kills (%)",
    "cs_per_min": "Farm / min",
    "gold_per_min": "Gold / min",
    "damage_dealt_per_min": "Dégâts / min",
    "vision_score_per_min": "Vision / min",
    "vision_control_per_min": "Contrôle Vision / min",
    "cc_score_per_min": "Contrôle de foule (CC) / min",
    "healing_on_teammates_per_min": "Soin Alliés / min",
    "effective_tanking_per_min": "Tanking Efficace / min",
    "team_damage_percentage": "Part Dégâts Équipe (%)"
}


def analyze_feature_trend(feature_name, feature_values, shap_values):
    """
    Détermine si une feature doit être maximisée ou minimisée.
    Regarde la corrélation entre la valeur de la stat et son impact (SHAP).
    """
    correlation = np.corrcoef(feature_values, shap_values)[0, 1]
    if correlation > 0.3:
        return "Plus c'est haut, mieux c'est 📈"
    elif correlation < -0.3:
        return "Attention à ne pas en faire trop (Rendements décroissants) 📉"
    else:
        return "Impact situationnel ⚖️"


def get_meta_analysis(role):
    """
    Génère une analyse complète (Image SHAP + Conseils) pour un rôle donné.
    """
    role = role.upper()
    db_path = config.get("db_path")
    conn = sqlite3.connect(db_path)

    try:
        # 1. Récupération des données
        df = get_all_historical_data(conn)
        role_df = df[df['role'] == role]

        if len(role_df) < 10:
            return jsonify({"error": f"Pas assez de données pour {role} (min 10 parties)"}), 400

        # Features à analyser
        features_list = [
            "kda", "kill_participation", "cs_per_min", "gold_per_min",
            "damage_dealt_per_min", "team_damage_percentage", "vision_score_per_min",
            "vision_control_per_min", "cc_score_per_min", "healing_on_teammates_per_min",
            "shields_on_teammates_per_min", "effective_tanking_per_min"
        ]
        # Filtrer celles qui existent
        valid_features = [f for f in features_list if f in role_df.columns]

        X = role_df[valid_features]
        y = role_df['win']

        # 2. Entraînement Modèle
        model = xgb.XGBClassifier(
            use_label_encoder=False, eval_metric='logloss', max_depth=3)
        model.fit(X, y)

        # 3. Calcul SHAP
        explainer = shap.Explainer(model, X)
        shap_values = explainer(X)

        # 4. Génération de l'Image (SHAP Summary)
        plt.figure(figsize=(10, 6))
        plt.title(f"Meta Analysis : {role}", fontsize=16, fontweight='bold')

        # On renomme les colonnes pour l'affichage
        X_display = X.rename(columns=READABLE_NAMES)

        shap.summary_plot(shap_values, X_display,
                          show=False, plot_size=(10, 6))

        # Sauvegarde dans un buffer mémoire
        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
        plt.close()
        buf.seek(0)
        image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

        # 5. Génération des "Conseils Tactiques" (Texte)
        # On calcule l'importance moyenne absolue des SHAP values
        feature_importance = pd.DataFrame({
            'feature': valid_features,
            'importance': np.abs(shap_values.values).mean(axis=0)
        }).sort_values(by='importance', ascending=False)

        tips = []
        for index, row in feature_importance.head(5).iterrows():
            feat = row['feature']
            trend = analyze_feature_trend(
                feat, X[feat], shap_values.values[:, index])
            readable_name = READABLE_NAMES.get(feat, feat)

            tips.append({
                "name": readable_name,
                "importance_score": round(row['importance'], 3),
                "tip": trend
            })

        return jsonify({
            "role": role,
            "image_base64": image_base64,
            "tactical_tips": tips
        })

    except Exception as e:
        print(f"Erreur Meta Analysis: {e}")
        return jsonify({"error": str(e)}), 500
    finally:
        conn.close()
