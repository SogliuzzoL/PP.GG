import os
import sqlite3
import sys

import numpy as np
import pandas as pd
from tqdm import tqdm

from backend.app import create_app
from backend.app.repositories.player_repository import PlayerRepository
from backend.app.services.analytics_service import AnalyticsService
from backend.app.services.scoring_service import ScoringService
from backend.app.utils.db import get_db_connection

# Configuration du chemin pour que Python trouve le module 'backend'
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))


def reset_skills_and_weights():
    """
    Nettoie les tables liées à l'apprentissage pour repartir de zéro.
    On garde les joueurs et les matchs, mais on efface leur MMR et les poids appris.
    """
    conn = get_db_connection()
    print("🧹 Nettoyage des tables 'player_skill' et 'performance_weights'...")
    try:
        conn.execute("DELETE FROM player_skill")
        conn.execute("DELETE FROM performance_weights")
        # Optionnel : Si tu veux aussi effacer l'historique des changements de Riot ID, décommente :
        # conn.execute("DELETE FROM player_riot_id_history")
        conn.commit()
    except Exception as e:
        print(f"❌ Erreur lors du reset : {e}")
    finally:
        conn.close()


def get_matches_chronologically():
    """Récupère tous les ID de matchs triés par date de création."""
    conn = get_db_connection()
    matches = conn.execute(
        "SELECT match_id, game_duration, winner FROM matches ORDER BY match_id ASC").fetchall()
    conn.close()
    return matches


def get_match_players_data(match_id, duration):
    """
    Reconstruit l'objet 'players_processing_list' tel qu'il est utilisé dans MatchService,
    à partir des données brutes stockées dans 'player_match_stats'.
    """
    conn = get_db_connection()
    stats_rows = conn.execute("""
        SELECT pms.*, p.riot_id, p.puuid 
        FROM player_match_stats pms
        JOIN players p ON pms.player_id = p.player_id
        WHERE pms.match_id = ?
    """, (match_id,)).fetchall()
    conn.close()

    players_list = []

    # Sécurité pour éviter la division par zéro
    duration = max(1, duration)

    for row in stats_rows:
        # Reconstitution des métriques (/min) comme dans MatchService
        # Note : Certaines métriques complexes (healing_teammates) dépendent de ta DB.
        # Assure-toi que les colonnes existent dans player_match_stats.

        metrics = {
            "kda": (row["kills"] + row["assists"]) / max(1, row["deaths"]),
            "kills_per_min": row["kills"] / duration,
            "deaths_per_min": row["deaths"] / duration,
            "assists_per_min": row["assists"] / duration,
            "gold_per_min": row["gold_earned"] / duration,
            "damage_dealt_per_min": row["total_damage_dealt_to_champions"] / duration,
            "vision_score_per_min": row["vision_score"] / duration,
            "cs_per_min": row["cs"] / duration,
            # Reconstruction approximative si certaines colonnes manquent,
            # sinon on utilise les valeurs directes
            "cc_score_per_min": row["time_ccing_others"] / duration,
            "healing_on_teammates_per_min": row["total_heal_on_teammates"] / duration,
            "shields_on_teammates_per_min": row["total_damage_shielded_on_teammates"] / duration,
            "effective_tanking_per_min": (
                row["total_damage_self_mitigated"] +
                (row["total_heal"] - row["total_heal_on_teammates"])
            ) / duration,
            # Vision control nécessite wards_killed et vision_wards_bought qui sont dans la DB
            "vision_control_per_min": (
                row["wards_killed"] * 1.5 + row["vision_wards_bought_in_game"]
            ) / duration,
        }

        # Calculs dépendant de l'équipe (Kill Participation, Dmg %)
        # Ces calculs sont simplifiés ici car nous traitons joueur par joueur,
        # mais idéalement il faudrait les totaux de l'équipe.
        # Pour un script de rescore rapide, l'approximation ou la récupération du total team est nécessaire.
        # Ici, on utilise les colonnes 'total_team_kills' et 'total_team_damage' stockées en base.

        if row["total_team_kills"] > 0:
            metrics["kill_participation"] = (
                row["kills"] + row["assists"]) / row["total_team_kills"] * 100
        else:
            metrics["kill_participation"] = 0

        if row["total_team_damage"] > 0:
            metrics["team_damage_percentage"] = (
                row["total_damage_dealt_to_champions"] / row["total_team_damage"]) * 100
        else:
            metrics["team_damage_percentage"] = 0

        # Détermination du display_side
        display_side = "Blue" if row["team_side"] == "bot" else "Red"

        players_list.append({
            "player_id": row["player_id"],
            "riot_id": row["riot_id"],
            "role": row["role"],
            "is_winner": bool(row["is_winner"]),
            "metrics": metrics,
            "team_side": row["team_side"],
            "display_side": display_side,
            "champion": row["champion_name"]
        })

    return players_list


def run_rescore():
    app = create_app()

    with app.app_context():
        print("🚀 Démarrage du processus de RE-SCORING...")

        # 1. Reset
        reset_skills_and_weights()

        # 2. Initialisation des services
        scoring_service = ScoringService()
        analytics_service = AnalyticsService()
        player_repo = PlayerRepository()

        # 3. Récupération de l'historique
        matches = get_matches_chronologically()
        print(f"📅 {len(matches)} matchs trouvés à rejouer.")

        # Historique global pour l'entraînement RLS initial
        # Au début c'est vide, mais le service gère le cas vide.
        # Pour être propre, on pourrait recharger le DF à chaque itération ou par batch,
        # mais ScoringService.ensure_models_up_to_date fait déjà une requête SQL.

        # 4. Boucle de replay
        for match_row in tqdm(matches, desc="Replaying Matches"):
            match_id = match_row["match_id"]
            duration = match_row["game_duration"]

            # A. Reconstitution des données joueurs
            players_processing_list = get_match_players_data(
                match_id, duration)
            if not players_processing_list:
                continue

            # B. Calcul du Skill Moyen du lobby (avant update)
            avg_skill_acc = 0
            for p in players_processing_list:
                curr_skill = player_repo.get_skill(p["player_id"])
                avg_skill_acc += curr_skill[0] if curr_skill else 50.0

            avg_match_skill = avg_skill_acc / len(players_processing_list)

            # C. Mise à jour des modèles (RLS Feature Selection)
            # Note : Pour optimiser, on peut ne pas le faire à *chaque* match si c'est lent,
            # mais pour la précision maximale, on le laisse.
            # Il faut récupérer le dataframe historique courant.
            # Attention : C'est l'opération la plus lourde.
            # Tu peux commenter ces deux lignes si tu veux juste recalculer le MMR sans changer les features dynamiques.
            # from backend.app.repositories.match_repository import MatchRepository
            # hist_df = MatchRepository().get_historical_data_dataframe()
            # scoring_service.ensure_models_up_to_date(hist_df)

            # D. Calcul des scores (RLS)
            players_processing_list = scoring_service.calculate_match_scores(
                players_processing_list)

            # E. Calcul du Shadow Score (XGBoost)
            # On suppose que le modèle XGBoost est statique ou géré par ailleurs.
            players_processing_list = analytics_service.compute_shadow_scores(
                match_id, players_processing_list)

            # F. Mise à jour du MMR (Kalman)
            final_players = scoring_service.update_player_skills(
                players_processing_list,
                avg_match_skill,
                score_key='shadow_score'
            )

            # G. Mise à jour des poids RLS (Apprentissage continu)
            scoring_service.update_rls_weights(final_players)

        print("✅ Re-scoring terminé avec succès !")


if __name__ == "__main__":
    run_rescore()
