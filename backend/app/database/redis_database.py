import os
import json
import redis.asyncio as aioredis
from typing import Optional, Any

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# Client Redis global
redis_client: Optional[aioredis.Redis] = None


async def get_redis() -> aioredis.Redis:
    """Dependency FastAPI pour obtenir le client Redis"""
    return redis_client


async def init_redis():
    """Initialiser Redis au démarrage de l'app"""
    global redis_client
    redis_client = aioredis.from_url(
        REDIS_URL,
        encoding="utf-8",
        decode_responses=True,
        max_connections=20,
    )
    await redis_client.ping()
    print("✅ Redis connecté !")


async def close_redis():
    """Fermer Redis à l'arrêt de l'app"""
    global redis_client
    if redis_client:
        await redis_client.aclose()
        print("🔴 Redis déconnecté.")


# ============================================================
# 🔴 BLACKLIST JWT (logout)
# ============================================================

async def blacklist_token(token: str, ttl_seconds: int = 86400):
    """Ajouter un token à la blacklist — expire après 24h"""
    await redis_client.setex(f"blacklist:{token}", ttl_seconds, "1")


async def is_token_blacklisted(token: str) -> bool:
    """Retourne True si le token est blacklisté (utilisateur déconnecté)"""
    result = await redis_client.get(f"blacklist:{token}")
    return result is not None


# ============================================================
# 💾 CACHE API
# ============================================================

async def cache_get(key: str) -> Optional[Any]:
    """Lire depuis le cache Redis"""
    value = await redis_client.get(f"cache:{key}")
    if value:
        return json.loads(value)
    return None


async def cache_set(key: str, value: Any, ttl_seconds: int = 300):
    """Écrire dans le cache Redis (défaut: 5 minutes)"""
    await redis_client.setex(f"cache:{key}", ttl_seconds, json.dumps(value, default=str))


async def cache_delete(key: str):
    """Supprimer une clé du cache"""
    await redis_client.delete(f"cache:{key}")


async def cache_delete_pattern(pattern: str):
    """Supprimer toutes les clés qui matchent un pattern"""
    keys = await redis_client.keys(f"cache:{pattern}")
    if keys:
        await redis_client.delete(*keys)


# ============================================================
# 👤 SESSIONS UTILISATEUR
# ============================================================

async def session_create(user_id: str, data: dict, ttl_seconds: int = 604800):
    """Créer une session utilisateur — expire après 7 jours"""
    await redis_client.setex(f"session:{user_id}", ttl_seconds, json.dumps(data, default=str))


async def session_get(user_id: str) -> Optional[dict]:
    """Récupérer les données de session d'un utilisateur"""
    value = await redis_client.get(f"session:{user_id}")
    if value:
        return json.loads(value)
    return None


async def session_delete(user_id: str):
    """Supprimer la session (logout)"""
    await redis_client.delete(f"session:{user_id}")


async def session_refresh(user_id: str, ttl_seconds: int = 604800):
    """Prolonger la durée de vie de la session"""
    await redis_client.expire(f"session:{user_id}", ttl_seconds)


# ============================================================
# 🚦 RATE LIMITING
# ============================================================

async def rate_limit_check(
    identifier: str,
    max_requests: int = 100,
    window_seconds: int = 60
) -> tuple[bool, int, int]:
    """
    Vérifie si l'identifiant a dépassé la limite.
    Retourne: (autorisé, nb_requêtes, nb_restantes)
    """
    key = f"ratelimit:{identifier}"
    count = await redis_client.incr(key)
    if count == 1:
        await redis_client.expire(key, window_seconds)
    allowed = count <= max_requests
    remaining = max(0, max_requests - count)
    return allowed, count, remaining