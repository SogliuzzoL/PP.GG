import numpy as np


class RecursiveLeastSquares:
    def __init__(self, n_features: int, lambda_: float = 0.99):
        self.n_features = n_features
        self.lambda_ = lambda_  # Facteur d'oubli
        # Poids initiaux positifs
        self.weights = np.array([0.25 for _ in range(n_features)])
        self.P = np.eye(n_features) * 1000  # Matrice de covariance initiale

    def update(self, x: np.ndarray, y: float) -> np.ndarray:
        # Prédiction : Mise à jour de la matrice de covariance
        self.P = self.P / self.lambda_

        # Calcul du gain de Kalman
        K = (self.P @ x) / (self.lambda_ + x.T @ self.P @ x)

        # Mise à jour des poids
        self.weights += K * (y - x.T @ self.weights)

        # Projection sur les valeurs positives
        self.weights = np.clip(self.weights, 10e-3, 10)

        # Mise à jour de la matrice de covariance
        self.P -= K[:, np.newaxis] * x.T @ self.P

        return self.weights


class KalmanSkillFilter:
    def __init__(self, mu0=50.0, sigma0=50/3, Q=0.1, R=1.0):
        self.mu = mu0          # Skill initial
        self.sigma2 = sigma0**2  # Variance initiale
        self.Q = Q            # Bruit de processus
        self.R = R            # Bruit de mesure

    def predict(self):
        self.mu_minus = self.mu
        self.sigma2_minus = self.sigma2 + self.Q

    def update(self, z):
        K = self.sigma2_minus / (self.sigma2_minus + self.R)
        self.mu = self.mu_minus + K * (z - self.mu_minus)
        self.sigma2 = (1 - K) * self.sigma2_minus

    def get_state(self):
        return self.mu, np.sqrt(self.sigma2)


def compute_performance_score(
    weights: dict,
    game_duration: float,
    kills: int,
    deaths: int,
    assists: int,
    cs: int,
    gold: int,
    damage_dealt: int,
    vision_score: int,
) -> float:
    """Calcule le score de performance normalisé."""
    kda = (kills + assists) / max(1, deaths)
    cs_per_minute = cs / max(1, game_duration)
    gold_per_minute = gold / max(1, game_duration) / 100
    damage_dealt_per_minute = damage_dealt / max(1, game_duration) / 100
    vision = vision_score / 10

    x = np.array([kda, cs_per_minute, gold_per_minute,
                 damage_dealt_per_minute, vision])

    score = (
        kda * weights["kda"] +
        cs_per_minute * weights["cs"] +
        gold_per_minute * weights["gold"] +
        damage_dealt_per_minute * weights["damage_dealt"] +
        vision * weights["vision_score"]
    )
    return x, score
