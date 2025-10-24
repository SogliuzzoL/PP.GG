import numpy as np
from config.weights import activate_weights


class RecursiveLeastSquares:
    def __init__(self, n_features: int, lambda_: float = 0.99):
        self.n_features = n_features
        self.lambda_ = lambda_  # Facteur d'oubli
        # Poids initiaux positifs
        self.weights = np.array([0.1 for _ in range(n_features)])
        self.P = np.eye(n_features) * 1000  # Matrice de covariance initiale

    def update(self, x: np.ndarray, y: float) -> np.ndarray:
        # Prédiction : Mise à jour de la matrice de covariance
        self.P = self.P / self.lambda_

        # Calcul du gain de Kalman
        K = (self.P @ x) / (self.lambda_ + x.T @ self.P @ x)

        # Mise à jour des poids
        self.weights += K * (y - x.T @ self.weights)

        # Projection sur les valeurs positives
        self.weights = np.clip(self.weights, 10e-5, 10)

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
    position: str,
    kills: int,
    deaths: int,
    assists: int,
    cs: int,
    gold: int,
    damage_dealt: int,
    vision_score: int,
    cc_score: int,
    healing_done: int,
    shield_amount: int,
    damage_blocked: int,
    heal: int
) -> float:
    """Calcule le score de performance normalisé."""
    kda = (kills + assists) / max(1, deaths)
    cs_per_minute = cs / max(1, game_duration)
    gold_per_minute = gold / max(1, game_duration) / 100
    damage_dealt_per_minute = damage_dealt / max(1, game_duration) / 100
    vision = vision_score / 10
    cc_per_minute = cc_score / max(1, game_duration)
    healing_per_minute = healing_done / max(1, game_duration) / 10
    shield_per_minute = shield_amount / max(1, game_duration) / 10
    damage_taken_per_minute = (damage_blocked + heal) / \
        max(1, game_duration) / 100

    x = np.array([kda, cs_per_minute, gold_per_minute, damage_dealt_per_minute, vision,
                 cc_per_minute, healing_per_minute, shield_per_minute, damage_taken_per_minute])

    score = (
        kda * weights.get("kda", 0) +
        cs_per_minute * weights.get("cs", 0) +
        gold_per_minute * weights.get("gold", 0) +
        damage_dealt_per_minute * weights.get("damage_dealt", 0) +
        vision * weights.get("vision_score", 0) +
        cc_per_minute * weights.get("cc_score", 0) +
        healing_per_minute * weights.get("healing_done", 0) +
        shield_per_minute * weights.get("shield_amount", 0) +
        damage_taken_per_minute * weights.get("damage_taken", 0)
    )

    x = []

    for feature in activate_weights[position]:
        if feature == "kda":
            x.append(kda)
        elif feature == "cs":
            x.append(cs_per_minute)
        elif feature == "gold":
            x.append(gold_per_minute)
        elif feature == "damage_dealt":
            x.append(damage_dealt_per_minute)
        elif feature == "vision_score":
            x.append(vision)
        elif feature == "cc_score":
            x.append(cc_per_minute)
        elif feature == "healing_done":
            x.append(healing_per_minute)
        elif feature == "shield_amount":
            x.append(shield_per_minute)
        elif feature == "damage_taken":
            x.append(damage_taken_per_minute)
    x = np.array(x)
    return x, score
