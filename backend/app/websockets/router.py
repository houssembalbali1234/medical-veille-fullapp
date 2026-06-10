from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Query
from app.websockets.manager import ws_manager
from app.database.redis_database import is_token_blacklisted
from jose import jwt, JWTError
import os
import asyncio
import json

router = APIRouter(tags=["WebSockets"])

SECRET = os.getenv("SECRET_KEY", "")
HEARTBEAT_INTERVAL = 30  # secondes


# ============================================================
# 🔐 AUTHENTIFICATION
# ============================================================

async def _authenticate(token: str, user_id: str) -> bool:
    """
    Vérifie le token JWT ET la blacklist Redis.
    Retourne True si valide, False sinon.
    """
    if not token:
        return False

    # ✅ Vérifier blacklist Redis (logout)
    if await is_token_blacklisted(token):
        return False

    try:
        payload = jwt.decode(token, SECRET, algorithms=["HS256"])
        decoded_user_id = payload.get("sub")
        # ✅ user_id URL doit correspondre au token
        return decoded_user_id == user_id
    except JWTError:
        return False


# ============================================================
# 🔌 ENDPOINT WEBSOCKET PRINCIPAL
# ============================================================

@router.websocket("/ws/{user_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    user_id: str,
    token: str = Query(..., description="JWT token pour authentification")
):
    """
    Endpoint WebSocket pour les notifications temps réel.

    Connexion :
        ws://localhost:8000/ws/{user_id}?token=<jwt_token>

    Messages reçus du serveur :
        {"type": "ping"}                      → Keepalive
        {"type": "connected", "data": {...}}  → Confirmation connexion
        {"type": "new_article", "data": ...}  → Nouvel article
        {"type": "alert", "data": ...}        → Alerte déclenchée
        {"type": "scraping_status", ...}      → Statut scraping

    Messages envoyés par le client :
        "ping"                                → String brut keepalive
        {"type": "pong"}                      → Réponse keepalive JSON
        {"type": "ping"}                      → Ping JSON
        {"type": "subscribe", "channel": ""} → S'abonner à un canal

    Codes de fermeture :
        4001 → Token invalide, révoqué ou user_id ne correspond pas
    """

    # ── 1. Authentification ────────────────────────────────
    is_valid = await _authenticate(token, user_id)
    if not is_valid:
        await websocket.close(code=4001, reason="Token invalide ou non autorisé")
        return

    # ── 2. Connexion ───────────────────────────────────────
    await ws_manager.connect(websocket, user_id)

    try:
        # Message de bienvenue
        await websocket.send_json({
            "type": "connected",
            "data": {
                "user_id": user_id,
                "message": "Connecté aux notifications temps réel ✅",
                "stats": ws_manager.get_stats()
            }
        })

        # ── 3. Boucle principale ───────────────────────────
        while True:
            try:
                # receive_text() supporte string brut ET JSON
                raw = await asyncio.wait_for(
                    websocket.receive_text(),
                    timeout=float(HEARTBEAT_INTERVAL)
                )
                await _handle_message(websocket, user_id, raw)

            except asyncio.TimeoutError:
                # Aucun message depuis 30s → envoyer ping
                await websocket.send_json({"type": "ping"})

    except WebSocketDisconnect:
        pass  # Déconnexion normale

    except Exception as e:
        print(f"⚠️ Erreur WebSocket user={user_id}: {e}")

    finally:
        # ✅ Toujours nettoyer, quoi qu'il arrive
        ws_manager.disconnect(websocket, user_id)


# ============================================================
# 📨 GESTION DES MESSAGES CLIENT
# ============================================================

async def _handle_message(websocket: WebSocket, user_id: str, raw: str):
    """
    Traite un message reçu du client.
    Supporte string brut ("ping") et JSON ({"type": "..."}).
    """
    # Ping string brut
    if raw.strip() == "ping":
        await websocket.send_json({"type": "pong"})
        return

    # Message JSON
    try:
        data = json.loads(raw)
    except json.JSONDecodeError:
        return  # Message invalide, ignorer

    msg_type = data.get("type", "")

    if msg_type == "pong":
        pass  # Réponse à notre ping → rien à faire

    elif msg_type == "ping":
        await websocket.send_json({"type": "pong"})

    elif msg_type == "subscribe":
        channel = data.get("channel", "all")
        await websocket.send_json({
            "type": "subscribed",
            "channel": channel
        })


# ============================================================
# 📊 STATS DES CONNEXIONS (admin)
# ============================================================

@router.get("/ws/stats", tags=["WebSockets"])
async def websocket_stats():
    """Statistiques des connexions WebSocket actives."""
    return ws_manager.get_stats()