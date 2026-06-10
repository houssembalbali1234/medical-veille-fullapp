from fastapi import WebSocket


class ConnectionManager:
    """
    Gestionnaire des connexions WebSocket.
    Maintient un registre de toutes les connexions actives
    organisées par user_id.
    """

    def __init__(self):
        # dict : user_id → set de WebSocket actifs
        # Un user peut avoir plusieurs connexions (multi-onglets)
        self.connections: dict[str, set[WebSocket]] = {}

    async def connect(self, websocket: WebSocket, user_id: str):
        """
        Accepte et enregistre une nouvelle connexion WebSocket.
        """
        await websocket.accept()

        if user_id not in self.connections:
            self.connections[user_id] = set()
        self.connections[user_id].add(websocket)

        print(f"🔌 WebSocket connecté — user_id={user_id} "
              f"(total connexions: {self.total_connections})")

    def disconnect(self, websocket: WebSocket, user_id: str):
        """
        Supprime une connexion du registre lors de la déconnexion.
        """
        if user_id in self.connections:
            self.connections[user_id].discard(websocket)

            # Nettoyer si plus de connexions pour cet utilisateur
            if not self.connections[user_id]:
                del self.connections[user_id]

        print(f"🔌 WebSocket déconnecté — user_id={user_id} "
              f"(total connexions: {self.total_connections})")

    @property
    def total_connections(self) -> int:
        """Nombre total de connexions WebSocket actives"""
        return sum(len(ws_set) for ws_set in self.connections.values())

    @property
    def active_users(self) -> int:
        """Nombre d'utilisateurs uniques connectés"""
        return len(self.connections)

    def is_user_connected(self, user_id: str) -> bool:
        """Vérifie si un utilisateur est connecté"""
        return user_id in self.connections and bool(self.connections[user_id])

    async def send_to_user(self, user_id: str, message: dict):
        """
        Envoie un message JSON à tous les clients d'un utilisateur.
        Gère automatiquement les connexions mortes.
        """
        if user_id not in self.connections:
            return  # Utilisateur non connecté, ignorer silencieusement

        dead_connections: set[WebSocket] = set()

        for websocket in self.connections[user_id].copy():
            try:
                await websocket.send_json(message)
            except Exception:
                dead_connections.add(websocket)

        # Nettoyer les connexions mortes
        for ws in dead_connections:
            self.connections[user_id].discard(ws)

        if not self.connections.get(user_id):
            self.connections.pop(user_id, None)

    async def broadcast_all(self, message: dict):
        """
        Envoie un message à TOUS les clients connectés.
        Utilisé pour les annonces globales (maintenance, nouvelles fonctionnalités).
        """
        dead_connections: dict[str, set[WebSocket]] = {}

        for user_id, ws_set in list(self.connections.items()):
            for websocket in ws_set.copy():
                try:
                    await websocket.send_json(message)
                except Exception:
                    if user_id not in dead_connections:
                        dead_connections[user_id] = set()
                    dead_connections[user_id].add(websocket)

        # Nettoyer les connexions mortes
        for user_id, dead_ws_set in dead_connections.items():
            if user_id in self.connections:
                for ws in dead_ws_set:
                    self.connections[user_id].discard(ws)
                if not self.connections[user_id]:
                    del self.connections[user_id]

    async def notify_new_article(self, user_id: str, article: dict):
        """
        Envoie une notification pour un nouvel article.
        """
        await self.send_to_user(user_id, {
            "type": "new_article",
            "data": {
                "pubmed_id":       article.get("pubmed_id"),
                "titre":           article.get("titre"),
                "specialite":      article.get("specialite"),
                "journal":         article.get("journal"),
                "annee":           article.get("annee"),
                "keyword_trigger": article.get("keyword_recherche"),
            }
        })

    async def notify_alert_triggered(
        self,
        user_id: str,
        notification_type: str,
        titre: str,
        message: str,
        pubmed_id: str | None = None
    ):
        """
        Envoie une notification d'alerte en temps réel.

        notification_type : "keyword" | "author" | "digest"
        """
        await self.send_to_user(user_id, {
            "type": "alert",
            "data": {
                "notification_type": notification_type,
                "titre":             titre,
                "message":           message,
                "pubmed_id":         pubmed_id,
            }
        })

    async def notify_scraping_status(
        self,
        keyword: str,
        source: str,
        status: str,
        nb_articles: int = 0
    ):
        """
        Diffuse le statut d'un scraping à tous les utilisateurs connectés.

        source  : "pubmed" | "europe_pmc" | "biorxiv"
        status  : "started" | "completed" | "error"
        """
        await self.broadcast_all({
            "type": "scraping_status",
            "data": {
                "keyword":     keyword,
                "source":      source,
                "status":      status,
                "nb_articles": nb_articles,
            }
        })

    async def send_ping(self, user_id: str):
        """Envoie un ping pour maintenir la connexion active"""
        await self.send_to_user(user_id, {"type": "ping"})

    def get_stats(self) -> dict:
        """Retourne les statistiques des connexions WebSocket"""
        return {
            "total_connections": self.total_connections,
            "active_users":      self.active_users,
            "users":             list(self.connections.keys()),
        }


# ============================================================
# 🌍 INSTANCE GLOBALE (Singleton)
# ============================================================
# Importé partout via :
#   from app.websocket_manager import ws_manager

ws_manager = ConnectionManager()