"""
socketio_route.py — Socket.io pour Medical Veille
==================================================
Socket.io offre des fonctionnalités avancées par rapport aux WebSockets natifs :
- Reconnexion automatique
- Rooms et namespaces
- Acknowledgements
- Fallback HTTP long-polling
"""

import socketio
import logging
import os
from jose import jwt, JWTError

logger = logging.getLogger("medical_veille.socketio")

SECRET = os.getenv("SECRET_KEY", "")

# ============================================================
# CONFIGURATION SOCKET.IO
# ============================================================

# Création du serveur Socket.io async
sio = socketio.AsyncServer(
    async_mode="asgi",
    cors_allowed_origins=[
        "http://localhost:3000",
        "http://localhost:3001",
        "http://127.0.0.1:3000",
        "http://127.0.0.1:3001",
    ],
    logger=False,
    engineio_logger=False,
)

# App ASGI pour Socket.io
socketio_app = socketio.ASGIApp(sio, socketio_path="socket.io")

# Dictionnaire des utilisateurs connectés
connected_users: dict[str, str] = {}  # sid -> user_id


# ============================================================
# AUTHENTIFICATION
# ============================================================

def authenticate_token(token: str) -> str | None:
    """Vérifie le token JWT et retourne le user_id."""
    if not token:
        return None
    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        return payload.get("sub")
    except JWTError:
        return None


# ============================================================
# ÉVÉNEMENTS SOCKET.IO
# ============================================================

@sio.event
async def connect(sid, environ, auth):
    """
    Connexion d'un client Socket.io.
    Le token JWT est passé dans auth : { token: "..." }
    """
    token = None
    if auth and isinstance(auth, dict):
        token = auth.get("token")

    user_id = authenticate_token(token) if token else None

    if not user_id:
        logger.warning(f"Socket.io connexion refusée — sid={sid}")
        raise ConnectionRefusedError("Token invalide")

    connected_users[sid] = user_id

    # Rejoindre la room personnelle
    await sio.enter_room(sid, f"user_{user_id}")

    logger.info(f"Socket.io connecté — user={user_id} sid={sid}")

    await sio.emit("connected", {
        "message": "Connecté via Socket.io !",
        "user_id": user_id,
        "active_users": len(set(connected_users.values()))
    }, to=sid)


@sio.event
async def disconnect(sid):
    """Déconnexion d'un client."""
    user_id = connected_users.pop(sid, None)
    logger.info(f"Socket.io déconnecté — user={user_id} sid={sid}")


@sio.event
async def ping(sid, data):
    """Répond au ping du client."""
    await sio.emit("pong", {"message": "pong"}, to=sid)


@sio.event
async def subscribe(sid, data):
    """
    Le client souscrit à un topic spécifique.
    Ex: { "topic": "alerts" }
    """
    topic = data.get("topic", "all") if isinstance(data, dict) else "all"
    await sio.enter_room(sid, f"topic_{topic}")
    await sio.emit("subscribed", {"topic": topic}, to=sid)
    logger.info(f"Socket.io subscribe — sid={sid} topic={topic}")


# ============================================================
# FONCTIONS D'ENVOI DE NOTIFICATIONS
# ============================================================

async def notify_user(user_id: str, event: str, data: dict):
    """Envoie une notification à un utilisateur spécifique."""
    room = f"user_{user_id}"
    await sio.emit(event, data, room=room)
    logger.info(f"Socket.io notification envoyée — user={user_id} event={event}")


async def notify_all(event: str, data: dict):
    """Envoie une notification à tous les utilisateurs connectés."""
    await sio.emit(event, data)
    logger.info(f"Socket.io broadcast — event={event}")


async def notify_topic(topic: str, event: str, data: dict):
    """Envoie une notification à tous les abonnés d'un topic."""
    room = f"topic_{topic}"
    await sio.emit(event, data, room=room)


def get_stats() -> dict:
    """Retourne les statistiques Socket.io."""
    return {
        "active_connections": len(connected_users),
        "active_users": len(set(connected_users.values())),
        "users": list(set(connected_users.values()))
    }