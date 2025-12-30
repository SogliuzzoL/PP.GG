import numpy as np
import pandas as pd

from backend.app.repositories.player_repository import PlayerRepository
from backend.app.repositories.weights_repository import WeightsRepository
from backend.app.services.math_engine import KalmanSkillFilter, RecursiveLeastSquares
from backend.app.utils.feature_selector import recommend_features


class ScoringService:
    def __init__(self):
        self.weights_repo = WeightsRepository()
        self.player_repo = PlayerRepository()
        # Fallback si pas assez de données pour recommander
        self.default_features = ["kda", "gold_per_min", "damage_dealt_per_min"]

    def ensure_models_up_to_date(self, historical_df):
        """
        Vérifie si les features utilisées sont optimales.
        Si non, ré-entraîne le modèle RLS sur l'historique.
        """
        if historical_df.empty:
            return

        # 1. Obtenir les recommandations basées sur la corrélation actuelle
        recommendations = recommend_features(historical_df)

        # Liste des rôles présents dans le jeu
        all_roles = ["TOP", "JUNGLE", "MIDDLE", "BOTTOM", "UTILITY"]

        for role in all_roles:
            # Quelles features devrions-nous utiliser ?
            recommended = recommendations.get(role, self.default_features)

            # Quelles features utilisons-nous actuellement ?
            stored_features, stored_weights, _ = self.weights_repo.get_weights(
                role)

            # Si changement ou pas de poids stockés -> RETRAINING
            if stored_features != recommended or stored_weights is None:
                print(
                    f"🔄 [Auto-Tuning] Changement détecté pour {role}. Ré-entraînement RLS...")
                print(f"   Ancien: {stored_features}")
                print(f"   Nouveau: {recommended}")

                self._retrain_model(role, recommended, historical_df)

    def _retrain_model(self, role, features, df, limit_games=50):
        """
        Ré-entraîne un modèle RLS 'à blanc' sur les X dernières parties
        pour initialiser les poids correctement.
        """
        rls = RecursiveLeastSquares(len(features))

        # Filtrer pour le rôle
        role_df = df[df['role'] == role].copy()
        if role_df.empty:
            # Sauvegarde des poids par défaut (0.01) si pas de données
            default_weights = {f: 0.01 for f in features}
            self.weights_repo.save_weights(
                role, features, default_weights, rls.P)
            return

        # On prend les X derniers matchs pour l'entraînement
        recent_matches = role_df['match_id'].unique()[-limit_games:]
        train_df = df[df['match_id'].isin(recent_matches)].copy()

        # --- Z-Score par Match (Logique critique pour la stabilité) ---
        # On doit normaliser les stats RELATIVEMENT à chaque partie spécifique
        for feat in features:
            if feat not in train_df.columns:
                train_df[feat] = 0.0
                continue

            # Moyenne/Std par match_id
            groups = train_df.groupby('match_id')[feat]
            mean = groups.transform('mean')
            std = groups.transform('std').replace(0, 1)  # Éviter div/0

            train_df[feat] = (train_df[feat] - mean) / std

        # Entraînement RLS séquentiel
        role_train_df = train_df[train_df['role'] == role]

        for _, row in role_train_df.iterrows():
            try:
                x = np.array([row[f] for f in features])
                # Cible : +1 (Victoire) / -1 (Défaite)
                y = 1.0 if row['win'] == 1 else -1.0
                rls.update(x, y)
            except Exception:
                continue

        # Sauvegarde des nouveaux poids optimisés
        new_weights = {f: float(w) for f, w in zip(features, rls.weights)}
        self.weights_repo.save_weights(role, features, new_weights, rls.P)
        print(f"✅ [Auto-Tuning] {role} optimisé. Poids: {new_weights}")

    def calculate_match_scores(self, players_data_list):
        # 1. Calcul Z-Scores (inchangé)
        feature_values = {}
        for p in players_data_list:
            for k, v in p['metrics'].items():
                feature_values.setdefault(k, []).append(v)

        z_scores_map = {}
        for feat, values in feature_values.items():
            mean = np.mean(values)
            std = np.std(values) if np.std(values) > 0 else 1.0
            for i, val in enumerate(values):
                z = (val - mean) / std
                z_scores_map.setdefault(i, {})[feat] = z

        # 2. RLS Scoring
        scored_players = []
        for i, p in enumerate(players_data_list):
            role = p['role']

            # Récupération (maintenant garantie à jour grâce à ensure_models_up_to_date)
            feats, w_dict, _ = self.weights_repo.get_weights(role)

            # Fallback ultime
            if not feats:
                feats = self.default_features
                w_dict = {f: 0.1 for f in feats}

            x_vec = np.array([z_scores_map[i].get(f, 0) for f in feats])
            w_vec = np.array([w_dict.get(f, 0) for f in feats])

            raw_score = np.dot(w_vec, x_vec)
            p['score_raw'] = raw_score
            p['feature_vector'] = x_vec
            p['active_features'] = feats
            scored_players.append(p)

        # 3. Normalisation (inchangé)
        raw_scores = [p['score_raw'] for p in scored_players]
        min_s, max_s = min(raw_scores), max(raw_scores)

        for p in scored_players:
            if max_s - min_s == 0:
                p['normalized_score'] = 50.0
            else:
                p['normalized_score'] = 20 + 60 * \
                    (p['score_raw'] - min_s) / (max_s - min_s)

        return scored_players

    def update_skills_and_weights(self, scored_players, avg_match_skill):
        updates_by_role = {}

        for p in scored_players:
            # --- Kalman Update ---
            current_mu, current_sigma = self.player_repo.get_skill(
                p['player_id']) or (50.0, 16.66)

            difficulty_bias = 0.5 * (avg_match_skill - current_mu)
            performance_target = p['normalized_score'] + difficulty_bias

            kf = KalmanSkillFilter(mu0=current_mu, sigma0=current_sigma)
            kf.predict()
            kf.update(performance_target)

            new_mu, new_sigma = kf.get_state()
            self.player_repo.save_skill(p['player_id'], new_mu, new_sigma)

            p['new_mu'] = new_mu
            p['new_sigma'] = new_sigma

            # --- RLS Prep ---
            target_y = 1.0 if p['is_winner'] else -1.0
            updates_by_role.setdefault(p['role'], []).append(
                (p['feature_vector'], target_y))

        # --- RLS Update (Apprentissage continu) ---
        for role, updates in updates_by_role.items():
            feats, w_dict, matrix_P = self.weights_repo.get_weights(role)
            if not feats:
                continue

            rls = RecursiveLeastSquares(len(feats))
            rls.weights = np.array([w_dict.get(f, 0) for f in feats])
            rls.P = matrix_P

            for x, y in updates:
                rls.update(x, y)

            new_w_dict = {f: float(w) for f, w in zip(feats, rls.weights)}
            self.weights_repo.save_weights(role, feats, new_w_dict, rls.P)

        return scored_players
