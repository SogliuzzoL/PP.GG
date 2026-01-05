from backend.app.utils.db import get_db_connection


class PlayerRepository:
    def get_player_id(self, puuid):
        conn = get_db_connection()
        cursor = conn.cursor()
        cursor.execute(
            "SELECT player_id FROM players WHERE puuid = ?", (puuid,))
        res = cursor.fetchone()
        conn.close()
        return res['player_id'] if res else None

    def create_player(self, puuid, riot_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        # MODIFICATION : On retire 'last_updated' de l'INSERT dans la table players
        cursor.execute(
            "INSERT INTO players (puuid, riot_id) VALUES (?, ?)",
            (puuid, riot_id)
        )
        pid = cursor.lastrowid

        # Historique Riot ID
        cursor.execute(
            "INSERT INTO player_riot_id_history (player_id, riot_id, changed_at) VALUES (?, ?, DATETIME('now'))",
            (pid, riot_id)
        )
        conn.commit()
        conn.close()
        return pid

    def update_riot_id(self, player_id, new_riot_id):
        conn = get_db_connection()
        cursor = conn.cursor()
        # MODIFICATION : On met à jour uniquement le riot_id, pas de last_updated ici
        cursor.execute(
            "UPDATE players SET riot_id = ? WHERE player_id = ?", (new_riot_id, player_id))

        # On ajoute une entrée à l'historique
        cursor.execute(
            "INSERT INTO player_riot_id_history (player_id, riot_id, changed_at) VALUES (?, ?, DATETIME('now'))",
            (player_id, new_riot_id)
        )
        conn.commit()
        conn.close()

    def get_skill(self, player_id):
        conn = get_db_connection()
        res = conn.execute(
            "SELECT mu, sigma FROM player_skill WHERE player_id = ?", (player_id,)).fetchone()
        conn.close()
        return (res['mu'], res['sigma']) if res else None

    def save_skill(self, player_id, mu, sigma):
        conn = get_db_connection()
        # UPSERT style
        exists = conn.execute(
            "SELECT 1 FROM player_skill WHERE player_id = ?", (player_id,)).fetchone()
        if exists:
            # last_updated est mis à jour ici, dans la table player_skill
            conn.execute(
                "UPDATE player_skill SET mu = ?, sigma = ?, last_updated = DATETIME('now') WHERE player_id = ?", (mu, sigma, player_id))
        else:
            conn.execute(
                "INSERT INTO player_skill (player_id, mu, sigma, last_updated) VALUES (?, ?, ?, DATETIME('now'))", (player_id, mu, sigma))
        conn.commit()
        conn.close()

    def get_top_players(self, limit=10, offset=0, days=30):
        conn = get_db_connection()
        # MODIFICATION CRITIQUE :
        # On filtre sur s.last_updated (skill) au lieu de p.last_updated (player)
        query = """
        SELECT p.riot_id, s.mu, s.sigma, (s.mu - 3 * s.sigma) as rating
        FROM players p
        JOIN player_skill s ON p.player_id = s.player_id
        WHERE s.last_updated > DATETIME('now', '-' || ? || ' days')
        ORDER BY rating DESC
        LIMIT ? OFFSET ?
        """
        rows = conn.execute(query, (days, limit, offset)).fetchall()
        conn.close()
        return [dict(row) for row in rows]

    def get_player_stats_history(self, riot_id):
        conn = get_db_connection()
        pid_row = conn.execute(
            "SELECT player_id FROM players WHERE riot_id = ?", (riot_id,)).fetchone()
        if not pid_row:
            conn.close()
            return None, None

        query = """
        SELECT pms.*, m.winner, m.game_duration
        FROM player_match_stats pms
        JOIN matches m ON pms.match_id = m.match_id
        WHERE pms.player_id = ?
        """
        rows = conn.execute(query, (pid_row['player_id'],)).fetchall()
        conn.close()
        return [dict(row) for row in rows], pid_row['player_id']

    def get_players_batch(self, riot_ids):
        """Récupère les stats pour une liste de Riot IDs."""
        if not riot_ids:
            return []

        conn = get_db_connection()
        placeholders = ','.join('?' for _ in riot_ids)
        query = f"""
            SELECT p.riot_id, s.mu, s.sigma
            FROM players p
            LEFT JOIN player_skill s ON p.player_id = s.player_id
            WHERE p.riot_id IN ({placeholders})
            """
        rows = conn.execute(query, riot_ids).fetchall()
        conn.close()
        return [dict(row) for row in rows]
