import base64
import io

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import shap
import xgboost as xgb

from backend.app.repositories.match_repository import MatchRepository

matplotlib.use('Agg')


class AnalyticsService:
    def __init__(self):
        self.match_repo = MatchRepository()
        self.readable_names = {
            "kda": "KDA", "kill_participation": "KP (%)", "cs_per_min": "CS/min",
            "gold_per_min": "Gold/min", "damage_dealt_per_min": "DPM",
            "vision_score_per_min": "Vis/min", "vision_control_per_min": "Vis. Ctrl/min",
            "cc_score_per_min": "CC/min", "healing_on_teammates_per_min": "Heal/min",
            "effective_tanking_per_min": "Tank/min", "team_damage_percentage": "Dmg%",
            "kills_per_min": "Kills/min", "deaths_per_min": "Deaths/min", "assists_per_min": "Assists/min"
        }

    def get_meta_analysis(self, role: str):
        """Génère l'analyse SHAP pour un rôle."""
        role = role.upper()
        df = self.match_repo.get_historical_data_dataframe()

        if df.empty:
            return {"error": "Aucune donnée historique disponible."}

        role_df = df[df['role'] == role]
        if len(role_df) < 5:  # Réduit à 5 pour faciliter les tests
            return {"error": f"Pas assez de données pour {role} (min 5 parties)."}

        # Sélection des features disponibles
        features_candidates = [
            "kda", "kill_participation", "cs_per_min", "gold_per_min",
            "damage_dealt_per_min", "team_damage_percentage", "vision_score_per_min",
            "vision_control_per_min", "cc_score_per_min", "healing_on_teammates_per_min",
            "shields_on_teammates_per_min", "effective_tanking_per_min",
            "kills_per_min", "deaths_per_min", "assists_per_min"
        ]

        # On ne garde que les colonnes qui existent vraiment dans le DF
        valid_features = [
            f for f in features_candidates if f in role_df.columns]

        if not valid_features:
            return {"error": "Aucune métrique calculée disponible."}

        X = role_df[valid_features]

        # CORRECTION ICI : Utilisation de 'win' au lieu de 'is_winner'
        if 'win' not in role_df.columns:
            return {"error": "Données de victoire manquantes pour l'entraînement."}

        y = role_df['win']

        # Vérification qu'il y a bien des victoires ET des défaites (sinon XGBoost plante)
        if y.nunique() <= 1:
            return {"error": "Besoin d'au moins 1 victoire et 1 défaite pour analyser les facteurs de succès."}

        # Entraînement
        try:
            model = xgb.XGBClassifier(
                use_label_encoder=False, eval_metric='logloss', max_depth=3)
            model.fit(X, y)

            # SHAP
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
                'feature': valid_features,
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
            print(f"Erreur XGBoost/SHAP: {e}")
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

        # Nettoyage
        numeric_df = role_df.select_dtypes(include=['number'])

        # On supprime les ID techniques s'ils traînent encore
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
        Range cible : 20 - 80.
        """
        print(
            f"🤖 [Shadow Mode] Calcul des scores XGBoost (Lissé) pour match #{current_match_id}...")

        df = self.match_repo.get_historical_data_dataframe()
        if df.empty or len(df) < 20:
            return players_data

        shadow_features = [
            "kda", "kill_participation", "cs_per_min", "gold_per_min",
            "damage_dealt_per_min", "team_damage_percentage",
            "vision_score_per_min", "vision_control_per_min",
            "cc_score_per_min", "healing_on_teammates_per_min",
            "shields_on_teammates_per_min", "effective_tanking_per_min"
        ]
        valid_features = [f for f in shadow_features if f in df.columns]

        roles_in_game = set(p['role'] for p in players_data)

        for role in roles_in_game:
            # On exclut le match actuel
            train_df = df[(df['role'] == role) & (
                df['match_id'] != current_match_id)]

            if len(train_df) < 10 or 'win' not in train_df.columns or train_df['win'].nunique() < 2:
                continue

            try:
                X_train = train_df[valid_features]
                y_train = train_df['win']

                # Paramètres conservateurs pour éviter les scores extrêmes (0.999)
                model = xgb.XGBClassifier(
                    n_estimators=50, max_depth=2, learning_rate=0.05,
                    use_label_encoder=False, eval_metric='logloss',
                    subsample=0.8  # Évite l'overfitting sur des patterns spécifiques
                )
                model.fit(X_train, y_train)

                for p in players_data:
                    if p['role'] == role:
                        p_feats = pd.DataFrame([p['metrics']])
                        p_input = pd.DataFrame(
                            0, index=[0], columns=valid_features)
                        for f in valid_features:
                            if f in p_feats.columns:
                                p_input[f] = p_feats[f]

                        # 1. Probabilité brute (0.0 -> 1.0)
                        raw_proba = model.predict_proba(p_input)[0][1]

                        # 2. Sigmoïde Centrée
                        # Formule : S(x) = 1 / (1 + exp(-k * (x - 0.5)))
                        # k définit la pente. k=5 est un bon équilibre.
                        # Si proba = 0.5 -> S = 0.5
                        # Si proba = 0.9 -> S ≈ 0.88
                        # Si proba = 0.1 -> S ≈ 0.12
                        k = 5
                        sigmoid_val = 1 / (1 + np.exp(-k * (raw_proba - 0.5)))

                        # 3. Scaling final vers 20-80
                        final_score = 20 + (sigmoid_val * 60)

                        p['shadow_score'] = final_score

            except Exception as e:
                print(f"   ❌ Erreur Shadow XGBoost pour {role}: {e}")

        return players_data
