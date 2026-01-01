import os

import xgboost as xgb


class ModelRepository:
    def __init__(self):
        self.model_dir = os.path.join(
            os.getcwd(), "backend", "models", "stored_models")
        os.makedirs(self.model_dir, exist_ok=True)

    def _get_model_path(self, role: str, model_type: str = "xgb") -> str:
        return os.path.join(self.model_dir, f"{role.lower()}_{model_type}.json")

    def save_model(self, model: xgb.XGBClassifier, role: str):
        path = self._get_model_path(role)
        model.save_model(path)
        print(f"💾 Modèle {role} sauvegardé sous {path}")

    def load_model(self, role: str) -> xgb.XGBClassifier:
        path = self._get_model_path(role)
        if not os.path.exists(path):
            return None

        # On recrée une instance vide pour charger les poids
        model = xgb.XGBClassifier()
        model.load_model(path)
        return model

    def delete_model(self, role: str):
        path = self._get_model_path(role)
        if os.path.exists(path):
            os.remove(path)
