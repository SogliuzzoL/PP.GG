import pandas as pd
import xgboost as xgb

from backend.app.repositories.match_repository import MatchRepository
from backend.app.repositories.model_repository import ModelRepository
from backend.config import Config


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
        self.feature_names_map = Config.FEATURES

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

        print(df)

        df = df.iloc[:-1]

        role_df = df[df['role'] == role]
        if len(role_df) < 10:  # Seuil minimal de sécurité
            print(f"⚠️ Pas assez de données pour entraîner {role}")
            return None

        features = [col for col in self.feature_names_map.keys()
                    if col in role_df.columns]

        X = role_df[features]
        y = role_df['win']

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
