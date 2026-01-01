import os
import pickle

import xgboost as xgb


class ModelRepository:
    def __init__(self):
        # Définit un dossier pour stocker les modèles
        self.model_dir = os.path.join(
            os.getcwd(), "backend", "models", "stored_models")
        os.makedirs(self.model_dir, exist_ok=True)

    def _get_model_path(self, role: str) -> str:
        # On passe à l'extension .pkl car on sauvegarde l'objet Python entier
        return os.path.join(self.model_dir, f"{role.lower()}_xgb.pkl")

    def save_model(self, model: xgb.XGBClassifier, role: str):
        path = self._get_model_path(role)
        try:
            with open(path, "wb") as f:
                pickle.dump(model, f)
            print(f"💾 Modèle {role} sauvegardé (Pickle) sous {path}")
        except Exception as e:
            print(f"❌ Erreur lors de la sauvegarde du modèle {role}: {e}")

    def load_model(self, role: str) -> xgb.XGBClassifier:
        path = self._get_model_path(role)
        if not os.path.exists(path):
            return None

        try:
            with open(path, "rb") as f:
                model = pickle.load(f)
            return model
        except Exception as e:
            print(
                f"⚠️ Erreur chargement modèle {role} (fichier corrompu ou version incompatible): {e}")
            # Si le fichier est corrompu, on peut vouloir le supprimer pour forcer un ré-entraînement
            return None

    def delete_model(self, role: str):
        path = self._get_model_path(role)
        if os.path.exists(path):
            os.remove(path)
