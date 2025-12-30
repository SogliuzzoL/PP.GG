import numpy as np
import xgboost as xgb


class KalmanSkillFilter:
    def __init__(self, mu0=50.0, sigma0=16.66, beta=5.0, tau=0.5):
        self.mu = mu0
        self.sigma = sigma0
        self.beta = beta
        self.tau = tau

    def predict(self):
        # Augmentation de l'incertitude avec le temps
        self.sigma = np.sqrt(self.sigma**2 + self.tau**2)

    def update(self, observed_performance):
        # observed_performance est le score normalisé du match
        # Kalman Gain
        k = (self.sigma**2) / (self.sigma**2 + self.beta**2)
        residual = observed_performance - self.mu

        self.mu = self.mu + k * residual
        self.sigma = np.sqrt((1 - k) * self.sigma**2)

    def get_state(self):
        return self.mu, self.sigma


class RecursiveLeastSquares:
    def __init__(self, n_features, lambda_factor=0.99):
        self.n = n_features
        self.weights = np.zeros(n_features)
        # Initialisation de P (Covariance) avec une grande diagonale
        self.P = np.eye(n_features) * 1000
        self.lambda_factor = lambda_factor

    def update(self, x, y):
        # x: vecteur de features (numpy array)
        # y: cible (ex: +1 pour win, -1 pour lose)
        x = x.reshape(-1, 1)
        # Calcul du gain
        Px = self.P @ x
        alpha = self.lambda_factor + (x.T @ Px)[0, 0]
        k = Px / alpha

        # Erreur de prédiction
        prediction = (self.weights @ x)[0]
        error = y - prediction

        # Mise à jour des poids
        self.weights = self.weights + (k.flatten() * error)

        # Mise à jour de P
        self.P = (self.P - k @ Px.T) / self.lambda_factor


class XGBoostModel:
    def __init__(self):
        self.model = xgb.XGBClassifier(
            n_estimators=100,
            max_depth=3,
            learning_rate=0.1,
            eval_metric='logloss'
        )

    def train(self, X, y):
        self.model.fit(X, y)

    def predict_proba(self, X):
        # Renvoie la probabilité de victoire (classe 1)
        return self.model.predict_proba(X)[:, 1]
