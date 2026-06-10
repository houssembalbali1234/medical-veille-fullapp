"""
Route WebSocket — /ws/notifications/{user_id}
=============================================
Connexion persistante pour les notifications temps réel.

Utilisation côté client (JavaScript) :
    const ws = new WebSocket("ws://localhost:8000/ws/notifications/USER_ID?token=JWT_TOKEN");

    ws.onopen = () => console.log("Connecté !");

    ws.onmessage = (event) => {
        const msg = JSON.parse(event.data);

        switch(msg.type) {
            case "connection":   console.log("Bienvenue !", msg);       break;
            case "alert":        showNotification(msg.data);             break;
            case "new_article":  addArticleToFeed(msg.data);            break;
            case "scraping_status": updateScrapingBadge(msg.data);      break;
            case "heartbeat":    ws.send("ping");                        break;
            case "pong":         console.log("pong reçu");              break;
        }
    };

    ws.onclose = (e) => console.log("Déconnecté", e.code, e.reason);
    ws.onerror = (e) => console.error("Erreur WebSocket", e);

Codes de fermeture personnalisés :
    4001 → Token manquant ou révoqué
    4003 → user_id URL ≠ user_id dans le token
    4004 → Token invalide ou expiré
"""

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.websockets.manager import ws_manager
from app.database.redis_database import is_token_blacklisted
from jose import jwt, JWTError
import os
import asyncio
import json
import logging

logger = logging.getLogger("medical_veille.websocket")

router = APIRouter(tags=["WebSockets"])

SECRET = os.getenv("SECRET_KEY", "")

# Durée avant d'envoyer un heartbeat (secondes)
HEARTBEAT_INTERVAL = 30


# ============================================================
# 🔐 AUTHENTIFICATION WEBSOCKET
# ============================================================

async def _authenticate_ws(token: str) -> str | None:
    """
    Authentifie un token JWT pour une connexion WebSocket.

    Retourne le user_id si le token est valide, None sinon.
    Les WebSockets ne supportent pas les headers HTTP custom
    → le token est passé en query param (?token=...).

    Vérifications :
    1. Token non vide
    2. Token non blacklisté (utilisateur déjà déconnecté)
    3. Signature JWT valide + non expiré
    4. Champ 'sub' (user_id) présent
    """
    if not token:
        return None

    # Vérifier blacklist Redis (logout)
    if await is_token_blacklisted(token):
        logger.warning("WebSocket auth refusée : token blacklisté")
        return None

    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        user_id = payload.get("sub")
        if not user_id:
            return None
        return user_id
    except JWTError as e:
        logger.warning(f"WebSocket auth refusée : token invalide ({e})")
        return None


# ============================================================
# 🔌 ENDPOINT WEBSOCKET PRINCIPAL
# ============================================================

@router.websocket("/ws/notifications/{user_id}")
async def websocket_notifications(
    websocket: WebSocket,
    user_id: str,
    token: str = Query(..., description="JWT Token d'authentification")
):
    """
    WebSocket de notifications temps réel.

    Flux de connexion :
    1. Client envoie le token JWT en query param
    2. Serveur vérifie le token + cohérence user_id
    3. Connexion acceptée → message de bienvenue
    4. Boucle : écoute les messages client + envoie heartbeat toutes les 30s
    5. Déconnexion propre sur WebSocketDisconnect ou erreur réseau
    """

    # ── 1. Authentification ────────────────────────────────
    authenticated_user_id = await _authenticate_ws(token)

    if not authenticated_user_id:
        await websocket.close(code=4001, reason="Token invalide ou révoqué")
        logger.warning(f"WebSocket refusé (token invalide) — user_id={user_id}")
        return

    # ── 2. Vérification cohérence URL vs token ─────────────
    # Empêche user A d'écouter les notifs de user B
    if authenticated_user_id != user_id:
        await websocket.close(code=4003, reason="user_id ne correspond pas au token")
        logger.warning(
            f"WebSocket refusé (mismatch) — "
            f"url={user_id} token={authenticated_user_id}"
        )
        return

    # ── 3. Connexion acceptée ──────────────────────────────
    await ws_manager.connect(websocket, user_id)
    stats = ws_manager.get_stats()
    logger.info(f"WebSocket connecté — user={user_id} | stats={stats}")

    try:
        # Message de bienvenue
        await websocket.send_json({
            "type": "connection",
            "message": "Connecté aux notifications temps réel !",
            "user_id": user_id,
            "stats": {
                "active_users":      stats["active_users"],
                "total_connections": stats["total_connections"],
            }
        })

        # ── 4. Boucle principale ───────────────────────────
        while True:
            try:
                # Attendre un message client avec timeout
                # Si timeout → envoyer heartbeat pour garder la connexion vivante
                raw = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=float(HEARTBEAT_INTERVAL)
                )

                await _handle_client_message(websocket, user_id, raw)

            except asyncio.TimeoutError:
                # Aucun message reçu depuis HEARTBEAT_INTERVAL secondes
                # → envoyer un heartbeat pour vérifier que le client est vivant
                try:
                    await websocket.send_json({"type": "heartbeat"})
                except Exception:
                    # Client ne répond plus → sortir de la boucle
                    logger.info(f"WebSocket client injoignable — user={user_id}")
                    break

    except WebSocketDisconnect as e:
        logger.info(f"WebSocket déconnecté normalement — user={user_id} code={e.code}")

    except Exception as e:
        logger.error(f"WebSocket erreur inattendue — user={user_id} : {e}")

    finally:
        # ── 5. Nettoyage toujours exécuté ─────────────────
        ws_manager.disconnect(websocket, user_id)
        logger.info(f"WebSocket nettoyé — user={user_id}")


# ============================================================
# 📨 GESTION DES MESSAGES CLIENT
# ============================================================

async def _handle_client_message(
    websocket: WebSocket,
    user_id: str,
    raw: str
):
    """
    Traite les messages reçus du client WebSocket.

    Messages supportés :
    - "ping"                          → répond {"type": "pong"}
    - {"type": "ping"}                → répond {"type": "pong"}
    - {"type": "subscribe", "topic"}  → confirme la souscription
    """
    # Ping simple (string brut)
    if raw.strip() == "ping":
        await websocket.send_json({"type": "pong"})
        return

    # Message JSON
    if raw.startswith("{"):
        try:
            msg = json.loads(raw)
            msg_type = msg.get("type", "")

            if msg_type == "ping":
                await websocket.send_json({"type": "pong"})

            elif msg_type == "subscribe":
                # Le client souscrit à un topic spécifique
                # (ex: uniquement les alertes, pas le scraping)
                topic = msg.get("topic", "all")
                await websocket.send_json({
                    "type": "subscribed",
                    "topic": topic,
                    "message": f"Souscrit au topic '{topic}'"
                })
                logger.info(f"WebSocket subscribe — user={user_id} topic={topic}")

            elif msg_type == "unsubscribe":
                topic = msg.get("topic", "all")
                await websocket.send_json({
                    "type": "unsubscribed",
                    "topic": topic,
                })

            else:
                # Type inconnu — on l'ignore silencieusement
                logger.debug(f"WebSocket message inconnu — type={msg_type}")

        except json.JSONDecodeError:
            # Message mal formé — on l'ignore
            logger.debug(f"WebSocket message JSON invalide — user={user_id}")


# ============================================================
# 📊 ROUTES HTTP COMPLÉMENTAIRES
# ============================================================

@router.get("/ws/status", summary="Statut des connexions WebSocket actives")
async def websocket_status():
    """
    Retourne les statistiques des connexions WebSocket en cours.

    Utile pour le monitoring et le debugging.
    """
    stats = ws_manager.get_stats()
    return {
        "status":            "ok",
        "active_users":      stats["active_users"],
        "total_connections": stats["total_connections"],
        "connected_users":   stats["users"],
    }


@router.post(
    "/ws/notify/{user_id}",
    summary="Envoyer une notification manuelle (admin)"
)
async def send_manual_notification(user_id: str, message: str, title: str = "Notification"):
    """
    Envoie une notification manuelle à un utilisateur connecté.
    Utile pour les tests et les annonces admin.
    """
    is_connected = ws_manager.is_user_connected(user_id)

    if is_connected:
        await ws_manager.notify_alert_triggered(
            user_id=user_id,
            notification_type="admin",
            titre=title,
            message=message,
        )

    return {
        "sent":         is_connected,
        "user_id":      user_id,
        "user_online":  is_connected,
        "message":      "Notification envoyée" if is_connected else "Utilisateur hors ligne",
    }