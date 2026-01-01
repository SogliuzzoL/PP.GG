import base64
import io

import matplotlib
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import seaborn as sns
import shap
import xgboost as xgb

from backend.app.repositories.match_repository import MatchRepository

matplotlib.use('Agg')


class AnalyticsService:
    def __init__(self):
        self.match_repo = MatchRepository()
        self.readable_names = {
            "kda": "KDA", "kill_participation": "KP (%)", "cs_per_min": "CS/min",
            "gold_per_min": "Gold/min", "damage_dealt_per_min": "DPM",
            "vision_score_per_min": "Vis/min", "vision_control_per_min": "Vis. Ctrl/min",
            "cc_score_per_min": "CC/min", "healing_on_teammates_per_min": "Heal/min",
            "effective_tanking_per_min": "Tank/min", "team_damage_percentage": "Dmg%",
            "kills_per_min": "Kills/min", "deaths_per_min": "Deaths/min", "assists_per_min": "Assists/min"
        }

    def get_meta_analysis(self, role: str):
        """Génère l'analyse SHAP pour un rôle."""
        role = role.upper()
        df = self.match_repo.get_historical_data_dataframe()

        if df.empty:
            return {"error": "Aucune donnée historique disponible."}

        role_df = df[df['role'] == role]
        if len(role_df) < 5:  # Réduit à 5 pour faciliter les tests
            return {"error": f"Pas assez de données pour {role} (min 5 parties)."}

        # Sélection des features disponibles
        features_candidates = self.readable_names.keys()

        # On ne garde que les colonnes qui existent vraiment dans le DF
        valid_features = [
            f for f in features_candidates if f in role_df.columns]

        if not valid_features:
            return {"error": "Aucune métrique calculée disponible."}

        X = role_df[valid_features]

        # CORRECTION ICI : Utilisation de 'win' au lieu de 'is_winner'
        if 'win' not in role_df.columns:
            return {"error": "Données de victoire manquantes pour l'entraînement."}

        y = role_df['win']

        # Vérification qu'il y a bien des victoires ET des défaites (sinon XGBoost plante)
        if y.nunique() <= 1:
            return {"error": "Besoin d'au moins 1 victoire et 1 défaite pour analyser les facteurs de succès."}

        # Entraînement
        try:
            model = xgb.XGBClassifier(
                use_label_encoder=False, eval_metric='logloss', max_depth=3)
            model.fit(X, y)

            # SHAP
            explainer = shap.Explainer(model, X)
            shap_values = explainer(X)

            # Génération Image
            plt.figure(figsize=(10, 6))
            X_display = X.rename(columns=self.readable_names)
            shap.summary_plot(shap_values, X_display,
                              show=False, plot_size=(10, 6))

            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
            plt.close()
            buf.seek(0)
            image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

            # Conseils Tactiques
            feature_importance = pd.DataFrame({
                'feature': valid_features,
                'importance': np.abs(shap_values.values).mean(axis=0)
            }).sort_values(by='importance', ascending=False)

            tips = []
            for index, row in feature_importance.head(5).iterrows():
                feat = row['feature']
                trend = self._analyze_trend(
                    X[feat], shap_values.values[:, index])
                tips.append({
                    "name": self.readable_names.get(feat, feat),
                    "importance_score": round(row['importance'], 3),
                    "tip": trend
                })

            return {
                "role": role,
                "image_base64": image_base64,
                "tactical_tips": tips
            }
        except Exception as e:
            print(f"Erreur XGBoost/SHAP: {e}")
            return {"error": f"Erreur d'analyse : {str(e)}"}

    def get_correlation_matrix_image(self, role: str):
        """Génère une image de matrice de corrélation."""
        role = role.upper()
        df = self.match_repo.get_historical_data_dataframe()

        if df.empty:
            raise ValueError("Pas de données.")

        role_df = df[df['role'] == role]
        if len(role_df) < 2:
            raise ValueError(f"Pas assez de données pour {role}.")

        # Nettoyage
        numeric_df = role_df.select_dtypes(include=['number'])

        # On supprime les ID techniques s'ils traînent encore
        cols_drop = ['match_id', 'player_id', 'stat_id', 'mu', 'sigma']
        numeric_df = numeric_df.drop(
            columns=[c for c in cols_drop if c in numeric_df.columns])

        corr = numeric_df.corr()

        plt.figure(figsize=(12, 10))
        sns.heatmap(corr, annot=True, cmap='coolwarm',
                    fmt=".2f", vmin=-1, vmax=1)
        plt.title(f'Matrice de Corrélation - {role}')

        buf = io.BytesIO()
        plt.savefig(buf, format='png', bbox_inches='tight')
        plt.close()
        buf.seek(0)
        return buf

    def _analyze_trend(self, feature_values, shap_values):
        try:
            corr = np.corrcoef(feature_values, shap_values)[0, 1]
            if corr > 0.3:
                return "Plus c'est haut, mieux c'est 📈"
            elif corr < -0.3:
                return "Attention aux rendements décroissants 📉"
            return "Impact situationnel ⚖️"
        except:
            return "Analyse complexe"

    def compute_shadow_scores(self, current_match_id, players_data):
        """
        Calcule un score XGBoost lissé par une sigmoïde centrée (courbe en S).
        Range cible : 20 - 80.
        """
        print(
            f"🤖 [Shadow Mode] Calcul des scores XGBoost (Lissé) pour match #{current_match_id}...")

        df = self.match_repo.get_historical_data_dataframe()
        if df.empty or len(df) < 20:
            return players_data

        shadow_features = self.readable_names.keys()
        valid_features = [f for f in shadow_features if f in df.columns]

        roles_in_game = set(p['role'] for p in players_data)

        for role in roles_in_game:
            # On exclut le match actuel
            train_df = df[(df['role'] == role) & (
                df['match_id'] != current_match_id)]

            if len(train_df) < 10 or 'win' not in train_df.columns or train_df['win'].nunique() < 2:
                continue

            try:
                X_train = train_df[valid_features]
                y_train = train_df['win']

                # Paramètres conservateurs pour éviter les scores extrêmes (0.999)
                model = xgb.XGBClassifier(
                    n_estimators=50, max_depth=2, learning_rate=0.05,
                    use_label_encoder=False, eval_metric='logloss',
                    subsample=0.8  # Évite l'overfitting sur des patterns spécifiques
                )
                model.fit(X_train, y_train)

                for p in players_data:
                    if p['role'] == role:
                        p_feats = pd.DataFrame([p['metrics']])
                        p_input = pd.DataFrame(
                            0, index=[0], columns=valid_features)
                        for f in valid_features:
                            if f in p_feats.columns:
                                p_input[f] = p_feats[f]

                        # 1. Probabilité brute (0.0 -> 1.0)
                        raw_proba = model.predict_proba(p_input)[0][1]

                        # 2. Sigmoïde Centrée
                        # Formule : S(x) = 1 / (1 + exp(-k * (x - 0.5)))
                        # k définit la pente. k=5 est un bon équilibre.
                        # Si proba = 0.5 -> S = 0.5
                        # Si proba = 0.9 -> S ≈ 0.88
                        # Si proba = 0.1 -> S ≈ 0.12
                        k = 5
                        sigmoid_val = 1 / (1 + np.exp(-k * (raw_proba - 0.5)))

                        # 3. Scaling final vers 20-80
                        final_score = 20 + (sigmoid_val * 60)

                        p['shadow_score'] = final_score

            except Exception as e:
                print(f"   ❌ Erreur Shadow XGBoost pour {role}: {e}")

        return players_data

    def get_personal_shap_analysis(self, riot_id: str, role: str):
        """
        Génère un graphique SHAP Waterfall personnalisé.
        Compare les stats moyennes du joueur à la "base value" du modèle.
        """
        role = role.upper()
        df = self.match_repo.get_historical_data_dataframe()

        if df.empty:
            return {"error": "Pas de données historiques."}

        # 1. Récupérer les données globales pour l'entraînement
        role_df = df[df['role'] == role]
        if len(role_df) < 20:
            return {"error": f"Pas assez de données globales pour le rôle {role} (min 20)."}

        # 2. Récupérer les données du joueur
        # On suppose que 'riot_id' est présent ou qu'on filtre par player_id.
        # Si riot_id n'est pas dans le DF, il faut le récupérer via le repo.
        # Ici, on assume que le DF contient une colonne identifiant le joueur (ex: 'riot_id' ou 'name')
        # Si ce n'est pas le cas, adaptez le filtre ci-dessous.
        player_games = role_df[role_df['riot_id'] == riot_id]

        if len(player_games) < 3:
            return {"error": f"Tu dois jouer au moins 3 parties en {role} pour avoir une analyse perso."}

        # 3. Préparation des Features
        features = self.readable_names.keys()
        # Filtrer celles qui existent vraiment
        valid_features = [f for f in features if f in role_df.columns]

        # 1. Préparation X et y
        X = role_df[valid_features]
        y = role_df['win']

        # Pour l'affichage "Avg", on garde la moyenne classique
        server_avg = X.mean()

        try:
            # 2. Entraînement du modèle
            model = xgb.XGBClassifier(
                eval_metric='logloss', max_depth=3)
            model.fit(X, y)
            optimal_map = self._compute_ml_optimal(model, X, valid_features)

            # 3. Calcul SHAP classique
            player_avg = player_games[valid_features].mean().to_frame().T
            explainer = shap.Explainer(model, X)
            shap_values = explainer(player_avg)

            # 4. Création des Labels dynamiques
            new_labels = []
            for feat in valid_features:
                base_name = self.readable_names.get(feat, feat)

                s_avg = server_avg[feat]
                # On récupère l'optimal calculé par l'IA
                o_avg = optimal_map.get(feat, 0)

                # Formatage (entier ou décimal)
                if feat in ["damage_dealt_per_min", "gold_per_min", "effective_tanking_per_min"]:
                    fmt = "{:.0f}"
                else:
                    fmt = "{:.1f}"

                label = f"{base_name}\nAvg:{fmt.format(s_avg)} | Opt:{fmt.format(o_avg)}"
                new_labels.append(label)

            shap_values.feature_names = new_labels

            # 5. Génération du graph (Waterfall)
            plt.figure(figsize=(14, 8))
            shap.plots.waterfall(shap_values[0], max_display=10, show=False)
            plt.title(
                f"Analyse IA : {riot_id} ({role}) vs Optimal théorique", fontsize=14)

            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
            plt.close()
            buf.seek(0)
            image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

            # 6. Texte d'analyse
            vals = shap_values.values[0]
            top_indices = np.argsort(np.abs(vals))[::-1][:3]
            original_names = [self.readable_names.get(
                f, f) for f in valid_features]

            tips = []
            for idx in top_indices:
                val = vals[idx]
                # La clé interne (ex: cs_per_min)
                feat_key = valid_features[idx]
                name = original_names[idx]     # Le nom joli (ex: CS/min)

                p_val = player_avg.iloc[0, idx]
                o_val = optimal_map.get(feat_key, 0)

                # Comparaison Joueur vs Optimal IA
                if val > 0:
                    tips.append(
                        f"✅ **{name}** : Ta moyenne est de `{p_val:.1f}`. L'IA considère que `{o_val:.1f}` est parfait, tu t'en rapproches bien !")
                else:
                    diff = o_val - p_val
                    tips.append(
                        f"⚠️ **{name}** : Tu es à `{p_val:.1f}`. Pour maximiser tes chances, l'IA suggère de viser `{o_val:.1f}` (Manque: `{diff:+.1f}`).")

            return {
                "image_base64": image_base64,
                "text_analysis": tips
            }

        except Exception as e:
            print(f"Erreur: {e}")
            return {"error": f"Erreur interne : {e}"}

    def _compute_ml_optimal(self, model, X, features):
        """
        Méthode 3 : Trouve la valeur optimale pour chaque feature en maximisant 
        la probabilité de victoire prédite par le modèle (analyse Ceteris Paribus).
        """
        optimal_stats = {}
        # 1. On part d'un joueur "moyen" (toutes les stats à la moyenne du serveur)
        base_vector = X.mean().to_frame().T

        for feat in features:
            try:
                # 2. On définit une plage de recherche réaliste (du Min au Top 1%)
                # On évite le max absolu pour ne pas viser des outliers impossibles
                min_val = X[feat].min()
                max_val = X[feat].quantile(0.99)

                if min_val == max_val:
                    optimal_stats[feat] = max_val
                    continue

                # 3. On teste 50 valeurs différentes entre le min et le max
                test_values = np.linspace(min_val, max_val, 50)

                # 4. On crée un tableau où seule cette feature change
                batch = pd.concat([base_vector] * 50, ignore_index=True)
                batch[feat] = test_values

                # 5. On demande au modèle : "Quelle est la probabilité de victoire pour chaque valeur ?"
                # predict_proba renvoie [Prob_Defaite, Prob_Victoire] -> on prend l'index 1
                probas = model.predict_proba(batch)[:, 1]

                # 6. On garde la valeur qui donne le % de victoire le plus haut
                best_idx = np.argmax(probas)
                optimal_stats[feat] = test_values[best_idx]

            except Exception as e:
                print(f"⚠️ Erreur calcul optimal ML pour {feat}: {e}")
                optimal_stats[feat] = X[feat].mean()  # Fallback sur la moyenne

        return optimal_stats

    def analyze_specific_match(self, match_id, riot_id):
        """
        Analyse une partie spécifique pour un joueur donné.
        Génère un graphique Waterfall montrant pourquoi le modèle a donné ce score/cette prédiction.
        """
        df = self.match_repo.get_historical_data_dataframe()

        if df.empty:
            return {"error": "Aucune donnée disponible."}

        # 1. Retrouver la ligne spécifique du match
        # Assurez-vous que les types correspondent (int/str) selon votre BDD
        try:
            match_id_int = int(match_id)
            match_row = df[(df['match_id'] == match_id_int)
                           & (df['riot_id'] == riot_id)]
        except ValueError:
            return {"error": "ID de match invalide."}

        if match_row.empty:
            return {"error": f"Match {match_id} introuvable pour {riot_id}."}

        # On récupère les infos contextuelles
        target_game = match_row.iloc[0]
        role = target_game['role']
        win = target_game['win'] == 1

        # 2. Préparer les données d'entraînement (Tout le monde sur ce rôle)
        role_df = df[df['role'] == role]
        if len(role_df) < 10:
            return {"error": "Pas assez de données globales pour analyser ce rôle."}

        features = self.readable_names.keys()
        valid_features = [f for f in features if f in role_df.columns]

        X = role_df[valid_features]
        y = role_df['win']

        # La ligne de données du joueur pour ce match précis
        X_target = match_row[valid_features]

        try:
            # 3. Entraînement rapide du modèle explicatif
            model = xgb.XGBClassifier(
                use_label_encoder=False, eval_metric='logloss', max_depth=3)
            model.fit(X, y)

            # 4. Calcul SHAP pour cette instance unique
            explainer = shap.Explainer(model, X)
            shap_values = explainer(X_target)

            # --- Génération Graphique Waterfall ---
            plt.figure(figsize=(10, 6))

            # On renforce les noms des features pour l'affichage
            new_names = [self.readable_names.get(n, n) for n in valid_features]
            shap_values.feature_names = new_names

            # On affiche la première (et unique) instance
            shap.plots.waterfall(shap_values[0], max_display=8, show=False)

            title = f"Impact Stats: {riot_id} ({'Victoire' if win else 'Défaite'})"
            plt.title(title, fontsize=14)

            buf = io.BytesIO()
            plt.savefig(buf, format='png', bbox_inches='tight', dpi=100)
            plt.close()
            buf.seek(0)
            image_base64 = base64.b64encode(buf.getvalue()).decode('utf-8')

            # --- Analyse textuelle des facteurs clés ---
            # On trie les valeurs SHAP par impact absolu
            vals = shap_values.values[0]
            indices = np.argsort(np.abs(vals))[::-1]  # Descending sort

            key_factors = []
            for i in indices[:3]:  # Top 3 facteurs
                feat_key = valid_features[i]
                feat_name = self.readable_names.get(feat_key, feat_key)
                impact = vals[i]
                player_val = X_target.iloc[0][feat_key]

                # Interprétation simple
                if impact > 0:
                    desc = f"👍 **{feat_name}** ({player_val:.1f}) a grandement aidé."
                else:
                    desc = f"👎 **{feat_name}** ({player_val:.1f}) a pénalisé la perf."

                key_factors.append(desc)

            return {
                "match_id": match_id,
                "riot_id": riot_id,
                "role": role,
                "analysis_image": image_base64,
                "key_factors": key_factors
            }

        except Exception as e:
            print(f"Erreur analyse match: {e}")
            return {"error": "Impossible de générer l'analyse détaillée."}
