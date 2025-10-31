import numpy as np


class RecursiveLeastSquares:
    def __init__(self, n_features: int, lambda_: float = 0.99):
        self.n_features = n_features
        self.lambda_ = lambda_  # Facteur d'oubli
        self.weights = np.array([0.1 for _ in range(n_features)])
        self.P = np.eye(n_features) * 1000  # Matrice de covariance initiale

    def update(self, x: np.ndarray, y: float) -> np.ndarray:
        self.P = self.P / self.lambda_
        K = (self.P @ x) / (self.lambda_ + x.T @ self.P @ x)
        self.weights += K * (y - x.T @ self.weights)
        # Projection pour garder les poids positifs et stables
        self.weights = np.clip(self.weights, 10e-5, 100)
        self.P -= K[:, np.newaxis] * x.T @ self.P
        return self.weights


class KalmanSkillFilter:
    def __init__(self, mu0=50.0, sigma0=50/3, Q=0.1, R=1.0):
        self.mu = mu0
        self.sigma2 = sigma0**2
        self.Q = Q
        self.R = R

    def predict(self):
        self.mu_minus = self.mu
        self.sigma2_minus = self.sigma2 + self.Q

    def update(self, z):
        K = self.sigma2_minus / (self.sigma2_minus + self.R)
        self.mu = self.mu_minus + K * (z - self.mu_minus)
        self.sigma2 = (1 - K) * self.sigma2_minus

    def get_state(self):
        return self.mu, np.sqrt(self.sigma2)
