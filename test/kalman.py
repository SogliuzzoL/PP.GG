import numpy as np


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

# Exemple d'utilisation
kalman = KalmanSkillFilter(mu0=50.0, sigma0=10.0, Q=0.1, R=1.0)

# PerformanceScores normalisés
performance_scores = [np.random.normal(80, 15) for _ in range(5)]
for z in performance_scores:
    kalman.predict()
    kalman.update(z)
    mu, sigma = kalman.get_state()
    print(f"Skill: {mu:.2f} ± {sigma:.2f}")