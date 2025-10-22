import numpy as np


class RecursiveLeastSquares:
    def __init__(self, n_features: int, lambda_: float = 0.99):
        self.n_features = n_features
        self.lambda_ = lambda_  # Facteur d'oubli
        self.weights = np.array(
            [0.25 for _ in range(n_features)])  # Poids initiaux
        self.P = np.eye(n_features) * 1000  # Matrice de covariance initiale

    def update(self, x: np.ndarray, y: float) -> np.ndarray:
        # Prédiction : Mise à jour de la matrice de covariance
        self.P = self.P / self.lambda_

        # Calcul du gain de Kalman
        K = (self.P @ x) / (self.lambda_ + x.T @ self.P @ x)

        # Mise à jour des poids
        self.weights += K * (y - x.T @ self.weights)

        # Mise à jour de la matrice de covariance
        self.P -= K[:, np.newaxis] * x.T @ self.P

        return self.weights


# Exemple d'utilisation
n_features = 6  # KDA, CS/min, Gold/min, Damage/min, Vision Score, Win
rls = RecursiveLeastSquares(n_features, lambda_=0.99)

# Données d'entraînement (exemple pour 3 matchs)
# Chaque x_t est un vecteur de métriques, et y_t est la cible (ex: 1 pour victoire, 0 pour défaite)

# Voici les datas d'un match:
# [2.33, 5.78, 408.80, 755.60, 8, 1] -> 66.78
# [2.33, 4.94, 325.90, 289.64, 7, 1] -> 38.41
# [5.50, 5.84, 437.71, 824.22, 1, 1] -> 69.77
# [7.50, 7.35, 512.11, 895.12, 5, 1] -> 80.79
# [4.00, 1.14, 409.10, 907.83, 24, 1] -> 80.92
# [1.20, 5.00, 361.81, 919.46, 8, 0] -> 71.16
# [1.20, 3.55, 358.01, 299.04, 11, 0] -> 40.73
# [1.00, 8.92, 578.98, 783.01, 8, 0] -> 77.06
# [0.62, 3.98, 274.58, 421.45, 4, 0] -> 39.10
# [0.50, 1.27, 256.51, 427.11, 14, 0] -> 42.06
training_data = [
    {"x": np.array([2.33, 5.78, 408.80, 755.60, 8, 1]), "y": 66.78},
    {"x": np.array([2.33, 4.94, 325.90, 289.64, 7, 1]), "y": 38.41},
    {"x": np.array([5.50, 5.84, 437.71, 824.22, 1, 1]), "y": 69.77},
    {"x": np.array([7.50, 7.35, 512.11, 895.12, 5, 1]), "y": 80.79},
    {"x": np.array([4.00, 1.14, 409.10, 907.83, 24, 1]), "y": 80.92},
    {"x": np.array([1.20, 5.00, 361.81, 919.46, 8, 0]), "y": 71.16},
    {"x": np.array([1.20, 3.55, 358.01, 299.04, 11, 0]), "y": 40.73},
    {"x": np.array([1.00, 8.92, 578.98, 783.01, 8, 0]), "y": 77.06},
    {"x": np.array([0.62, 3.98, 274.58, 421.45, 4, 0]), "y": 39.10},
    {"x": np.array([0.50, 1.27, 256.51, 427.11, 14, 0]), "y": 42.06},
]

# Mise à jour des poids pour chaque match
for data in training_data:
    rls.update(data["x"], data["y"])
    print(f"Poids mis à jour ")
    for weight, name in zip(rls.weights, ["KDA", "CS/min", "Gold/min", "Damage/min", "Vision Score", "Win"]):
        print(f"  {name}: {weight:.4f}")
    print(rls.P.trace())
