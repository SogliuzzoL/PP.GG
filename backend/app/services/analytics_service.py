import base64
import io
import os

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import shap
import xgboost as xgb
from matplotlib.backends.backend_pdf import PdfPages

from backend.app.repositories.match_repository import MatchRepository
from backend.app.services.ml_service import MachineLearningService
from backend.config import Config

matplotlib.use('Agg')


class AnalyticsService:
    def __init__(self):
        self.match_repo = MatchRepository()
        self.ml_service = MachineLearningService()
        self.readable_names = Config.FEATURES

    def get_meta_analysis(self, role: str):
        """Génère l'analyse SHAP pour un rôle en utilisant le modèle centralisé."""
        role = role.upper()

        # 1. Récupération du modèle unifié
        model = self.ml_service.get_or_train_model(role)
        if not model:
            return {"error": f"Pas assez de données ou modèle indisponible pour {role}."}

        # 2. Récupération des données pour l'explication SHAP
        df = self.match_repo.get_historical_data_dataframe()
        if df.empty:
            return {"error": "Aucune donnée historique disponible."}

        role_df = df[df['role'] == role]
        if len(role_df) < 5:
            return {"error": f"Pas assez de données pour l'analyse SHAP de {role}."}

        # 3. Alignement des features
        model_features = model.get_booster().feature_names
        available_features = [
            f for f in model_features if f in role_df.columns]

        if len(available_features) != len(model_features):
            pass

        X = role_df[model_features]

        try:
            # SHAP explainer sur le modèle déjà entraîné
            explainer = shap.Explainer(model, X)
            shap_values = explainer(X)

            # Génération Image
            plt.figure(figsize=(10, 6))
            X_display = X.rename(columns=self.readable_names)
            shap.summary_plot(shap_values, X_display,
                              show=False, plot_size=(10, 6))

            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
            plt.close()
            buf.seek(0)
            image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

            # Conseils Tactiques
            feature_importance = pd.DataFrame({
                'feature': model_features,
                'importance': np.abs(shap_values.values).mean(axis=0)
            }).sort_values(by='importance', ascending=False)

            tips = []
            for index, row in feature_importance.head(5).iterrows():
                feat = row['feature']
                trend = self._analyze_trend(
                    X[feat], shap_values.values[:, index])
                tips.append({
                    "name": self.readable_names.get(feat, feat),
                    "importance_score": round(row['importance'], 3),
                    "tip": trend
                })

            return {
                "role": role,
                "image_base64": image_base64,
                "tactical_tips": tips
            }
        except Exception as e:
            print(f"Erreur SHAP: {e}")
            return {"error": f"Erreur d'analyse : {str(e)}"}

    def get_correlation_matrix_image(self, role: str):
        """Génère une image de matrice de corrélation."""
        role = role.upper()
        df = self.match_repo.get_historical_data_dataframe()

        if df.empty:
            raise ValueError("Pas de données.")

        role_df = df[df['role'] == role]
        if len(role_df) < 2:
            raise ValueError(f"Pas assez de données pour {role}.")

        numeric_df = role_df.select_dtypes(include=['number'])
        cols_drop = ['match_id', 'player_id', 'stat_id', 'mu', 'sigma']
        numeric_df = numeric_df.drop(
            columns=[c for c in cols_drop if c in numeric_df.columns])

        corr = numeric_df.corr()

        plt.figure(figsize=(12, 10))
        sns.heatmap(corr, annot=True, cmap='coolwarm',
                    fmt=".2f", vmin=-1, vmax=1)
        plt.title(f'Matrice de Corrélation - {role}')

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return buf

    def _analyze_trend(self, feature_values, shap_values):
        try:
            corr = np.corrcoef(feature_values, shap_values)[0, 1]
            if corr > 0.3:
                return "Plus c'est haut, mieux c'est 📈"
            elif corr < -0.3:
                return "Attention aux rendements décroissants 📉"
            return "Impact situationnel ⚖️"
        except:
            return "Analyse complexe"

    def compute_shadow_scores(self, current_match_id, players_data):
        """
        Calcule un score XGBoost lissé par une sigmoïde centrée (courbe en S).
        """
        print(
            f"🤖 [Shadow Mode] Calcul des scores XGBoost pour match #{current_match_id}...")

        roles_in_game = set(p['role'] for p in players_data)

        for role in roles_in_game:
            model = self.ml_service.get_or_train_model(
                role, force_retrain=True)
            if not model:
                continue

            expected_features = model.get_booster().feature_names

            for p in players_data:
                if p['role'] == role:
                    try:
                        p_feats = pd.DataFrame([p['metrics']])
                        p_input = pd.DataFrame(
                            0, index=[0], columns=expected_features)

                        for f in expected_features:
                            if f in p_feats.columns:
                                p_input[f] = p_feats[f]

                        raw_proba = model.predict_proba(p_input)[0][1]

                        k = 5
                        sigmoid_val = 1 / (1 + np.exp(-k * (raw_proba - 0.5)))
                        final_score = 20 + (sigmoid_val * 60)
                        p['shadow_score'] = final_score

                    except Exception as e:
                        print(
                            f"   ❌ Erreur calcul Shadow pour {p.get('riot_id')} ({role}): {e}")

        return players_data

    def get_personal_shap_analysis(self, riot_id: str, role: str):
        """
        Génère un graphique SHAP Waterfall personnalisé.
        Compare les stats moyennes du joueur à la "base value" du modèle.
        """
        role = role.upper()

        # 1. Modèle unifié
        model = self.ml_service.get_or_train_model(role)
        if not model:
            return {"error": "Modèle indisponible."}

        df = self.match_repo.get_historical_data_dataframe()
        if df.empty:
            return {"error": "Pas de données historiques."}

        role_df = df[df['role'] == role]
        if len(role_df) < 20:
            return {"error": f"Pas assez de données globales pour {role}."}

        # 2. Données du joueur
        player_games = role_df[role_df['riot_id'] == riot_id]
        if len(player_games) < 1:
            return {"error": f"Tu dois jouer au moins une partie en {role} pour avoir une analyse perso."}

        # 3. Préparation Features
        valid_features = model.get_booster().feature_names
        X = role_df[valid_features]

        # Pour l'affichage "Avg", moyenne du serveur
        server_avg = X.mean()

        try:
            # 4. Calcul de l'optimal théorique via le modèle
            optimal_map = self._compute_ml_optimal(model, X, valid_features)

            # 5. Calcul SHAP classique sur la moyenne du joueur
            player_avg = player_games[valid_features].mean().to_frame().T
            explainer = shap.Explainer(model, X)
            shap_values = explainer(player_avg)

            # 6. Création des Labels dynamiques
            shap_values.feature_names = self._generate_comparison_labels(
                valid_features, server_avg, optimal_map)

            # 7. Génération du graph
            plt.figure(figsize=(14, 8))
            shap.plots.waterfall(shap_values[0], max_display=len(
                self.readable_names), show=False)
            plt.title(
                f"Analyse IA : {riot_id} ({role}) vs Optimal théorique", fontsize=14)

            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
            plt.close()
            buf.seek(0)
            image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

            # 8. Texte d'analyse
            vals = shap_values.values[0]
            top_indices = np.argsort(np.abs(vals))[::-1][:3]
            original_names = [self.readable_names.get(
                f, f) for f in valid_features]

            tips = []
            for idx in top_indices:
                feat_key = valid_features[idx]
                name = original_names[idx]
                p_val = player_avg.iloc[0, idx]
                o_val = optimal_map.get(feat_key, 0)
                val = vals[idx]

                if val > 0:
                    tips.append(
                        f"✅ **{name}** : Ta moyenne est de `{p_val:.1f}`. L'IA considère que `{o_val:.1f}` est parfait, tu t'en rapproches bien !")
                else:
                    diff = o_val - p_val
                    tips.append(
                        f"⚠️ **{name}** : Tu es à `{p_val:.1f}`. Pour maximiser tes chances, l'IA suggère de viser `{o_val:.1f}` (Manque: `{diff:+.1f}`).")

            return {
                "image_base64": image_base64,
                "text_analysis": tips
            }

        except Exception as e:
            print(f"Erreur: {e}")
            return {"error": f"Erreur interne : {e}"}

    def _compute_ml_optimal(self, model, X, features):
        """
        Trouve la valeur optimale pour chaque feature en maximisant
        la probabilité de victoire prédite par le modèle.
        """
        optimal_stats = {}
        base_vector = X.mean().to_frame().T

        for feat in features:
            try:
                min_val = X[feat].min()
                max_val = X[feat].quantile(0.99)

                if min_val == max_val:
                    optimal_stats[feat] = max_val
                    continue

                test_values = np.linspace(min_val, max_val, 50)
                batch = pd.concat([base_vector] * 50, ignore_index=True)
                batch[feat] = test_values

                probas = model.predict_proba(batch)[:, 1]
                best_idx = np.argmax(probas)
                optimal_stats[feat] = test_values[best_idx]

            except Exception as e:
                print(f"⚠️ Erreur calcul optimal ML pour {feat}: {e}")
                optimal_stats[feat] = X[feat].mean()

        return optimal_stats

    def _generate_comparison_labels(self, features, server_avg, optimal_map):
        """Génère les labels formattés Avg vs Opt pour les graphiques."""
        new_labels = []
        for feat in features:
            base_name = self.readable_names.get(feat, feat)
            s_avg = server_avg[feat]
            o_avg = optimal_map.get(feat, 0)

            if feat in ["damage_dealt_per_min", "gold_per_min", "effective_tanking_per_min"]:
                fmt = "{:.0f}"
            else:
                fmt = "{:.1f}"

            label = f"{base_name}\nAvg:{fmt.format(s_avg)} | Opt:{fmt.format(o_avg)}"
            new_labels.append(label)
        return new_labels

    def analyze_specific_match(self, match_id, riot_id):
        """
        Analyse une partie spécifique pour un joueur donné via le modèle central.
        Affiche désormais les comparaisons Optimales / Moyennes comme l'analyse perso.
        """
        df = self.match_repo.get_historical_data_dataframe()

        if df.empty:
            return {"error": "Aucune donnée disponible."}

        try:
            match_id_int = int(match_id)
            match_row = df[(df['match_id'] == match_id_int)
                           & (df['riot_id'] == riot_id)]
        except ValueError:
            return {"error": "ID de match invalide."}

        if match_row.empty:
            return {"error": f"Match {match_id} introuvable pour {riot_id}."}

        target_game = match_row.iloc[0]
        role = target_game['role']
        win = target_game['win'] == 1

        # Récupération Modèle
        model = self.ml_service.get_or_train_model(role)
        if not model:
            return {"error": "Pas de modèle disponible pour ce rôle."}

        # Contexte global pour SHAP et comparaisons
        role_df = df[df['role'] == role]
        valid_features = model.get_booster().feature_names
        X = role_df[valid_features]
        X_target = match_row[valid_features]

        # Calcul des références (Moyenne serveur et Optimal)
        server_avg = X.mean()

        try:
            optimal_map = self._compute_ml_optimal(model, X, valid_features)

            # SHAP
            explainer = shap.Explainer(model, X)
            shap_values = explainer(X_target)

            # Application des labels uniformisés (Avg | Opt)
            shap_values.feature_names = self._generate_comparison_labels(
                valid_features, server_avg, optimal_map)

            # Graphique Waterfall uniformisé
            plt.figure(figsize=(14, 8))
            shap.plots.waterfall(shap_values[0], max_display=len(
                valid_features), show=False)

            title = f"Impact Stats: {riot_id} ({'Victoire' if win else 'Défaite'})"
            plt.title(title, fontsize=14)

            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
            plt.close()
            buf.seek(0)
            image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

            # Analyse textuelle
            vals = shap_values.values[0]
            indices = np.argsort(np.abs(vals))[::-1]

            key_factors = []
            for i in indices[:3]:
                feat_key = valid_features[i]
                feat_name = self.readable_names.get(feat_key, feat_key)
                impact = vals[i]
                player_val = X_target.iloc[0][feat_key]

                if impact > 0:
                    desc = f"👍 **{feat_name}** ({player_val:.1f}) a grandement aidé."
                else:
                    desc = f"👎 **{feat_name}** ({player_val:.1f}) a pénalisé la perf."
                key_factors.append(desc)

            return {
                "match_id": match_id,
                "riot_id": riot_id,
                "role": role,
                "analysis_image": image_base64,
                "key_factors": key_factors
            }

        except Exception as e:
            print(f"Erreur analyse match: {e}")
            return {"error": "Impossible de générer l'analyse détaillée."}

    def save_all_trees_pdf(self, role):
        """Génère un PDF en mémoire (RAM) pour éviter les I/O disques et les timeouts."""
        role = role.upper()
        model = self.ml_service.get_or_train_model(role)

        n_trees = model.get_booster().num_boosted_rounds()
        print(f"📄 Génération du PDF en mémoire avec {n_trees} pages...")

        # Utilisation d'un buffer en mémoire (RAM) au lieu d'un fichier physique
        pdf_buffer = io.BytesIO()

        # Désactiver le mode interactif de matplotlib pour gagner un peu de perf
        plt.ioff()

        with PdfPages(pdf_buffer) as pdf:
            for i in range(n_trees):
                # Réduction légère de la taille (15, 10) pour accélérer le rendu sans trop perdre en lisibilité
                plt.figure(figsize=(15, 10))

                # CORRECTION DU WARNING : utilisation de 'tree_idx' au lieu de 'num_trees'
                xgb.plot_tree(model, tree_idx=i, rankdir='LR')
                plt.title(f"Arbre #{i} - {role}")
                pdf.savefig(bbox_inches='tight', dpi=250)

                # Fermeture explicite pour éviter la fuite de mémoire
                plt.close()

        # Rembobiner le buffer au début pour qu'il puisse être lu par Flask
        pdf_buffer.seek(0)

        print(f"✅ PDF généré avec succès ({n_trees} arbres).")
        return pdf_buffer
