import pandas as pd
import xgboost as xgb

from backend.app.repositories.match_repository import MatchRepository
from backend.app.repositories.model_repository import ModelRepository
from backend.app.utils.feature_selector import recommend_features


class MachineLearningService:
    def __init__(self):
        self.match_repo = MatchRepository()
        self.model_repo = ModelRepository()

        # Configuration UNIFORMISÉE pour tous les modèles
        self.xgb_params = {
            "n_estimators": 100,
            "max_depth": 3,           # Assez faible pour éviter l'overfitting sur peu de données
            "learning_rate": 0.05,
            "subsample": 0.8,         # Robustesse
            "eval_metric": "logloss"
        }

        # Mapping lisible pour SHAP (repris de ton analytics_service)
        self.feature_names_map = {
            "kda": "KDA", "kill_participation": "KP (%)", "cs_per_min": "CS/min",
            "gold_per_min": "Gold/min", "damage_dealt_per_min": "DPM",
            "vision_score_per_min": "Vis/min", "vision_control_per_min": "Vis. Ctrl/min",
            "cc_score_per_min": "CC/min", "healing_on_teammates_per_min": "Heal/min",
            "effective_tanking_per_min": "Tank/min", "team_damage_percentage": "Dmg%",
            "kills_per_min": "Kills/min", "deaths_per_min": "Deaths/min", "assists_per_min": "Assists/min"
        }

    def get_or_train_model(self, role: str, force_retrain: bool = False):
        """Récupère le modèle sauvegardé ou l'entraîne si inexistant/forcé."""
        role = role.upper()

        if not force_retrain:
            model = self.model_repo.load_model(role)
            if model:
                return model

        print(f"⚙️ Entraînement du modèle XGBoost pour {role}...")
        return self._train_model(role)

    def _train_model(self, role: str):
        df = self.match_repo.get_historical_data_dataframe()
        if df.empty:
            return None

        role_df = df[df['role'] == role]
        if len(role_df) < 10:  # Seuil minimal de sécurité
            print(f"⚠️ Pas assez de données pour entraîner {role}")
            return None

        # Sélection des features (tu peux réutiliser ton logic intelligent ou une liste fixe)
        # Pour l'uniformisation, je suggère de prendre toutes les colonnes numériques pertinentes
        # ou d'utiliser ta fonction 'recommend_features' ici.
        features = [col for col in self.feature_names_map.keys()
                    if col in role_df.columns]

        X = role_df[features]
        y = role_df['win']  # Assure-toi que c'est 0/1

        if y.nunique() < 2:
            return None

        model = xgb.XGBClassifier(**self.xgb_params)
        model.fit(X, y)

        # Sauvegarde automatique
        self.model_repo.save_model(model, role)
        return model

    def get_features_for_role(self, role):
        # Permet aux autres services de savoir quelles features le modèle attend
        model = self.get_or_train_model(role)
        if model:
            return model.get_booster().feature_names
        return []
