from fastapi import Request, HTTPException
from starlette.middleware.base import BaseHTTPMiddleware
from app.database.redis_database import rate_limit_check

EXEMPT_PATHS = {"/", "/docs", "/openapi.json", "/redoc", "/health", "/metrics"}


class RateLimitMiddleware(BaseHTTPMiddleware):
    """
    Middleware appliqué automatiquement sur toutes les routes.
    - /auth  → max 200 req/min
    - autres → max 500 req/min
    """

    async def dispatch(self, request: Request, call_next):
        path = request.url.path

        # Routes exemptées
        if path in EXEMPT_PATHS:
            return await call_next(request)

        # Identifier l'utilisateur par son IP
        client_ip = request.client.host if request.client else "unknown"

        # Limite sur /auth
        if path.startswith("/auth"):
            allowed, count, remaining = await rate_limit_check(
                identifier=f"auth:{client_ip}",
                max_requests=200,
                window_seconds=60
            )
        else:
            allowed, count, remaining = await rate_limit_check(
                identifier=f"api:{client_ip}",
                max_requests=500,
                window_seconds=60
            )

        if not allowed:
            raise HTTPException(
                status_code=429,
                detail={
                    "error": "Trop de requêtes",
                    "message": "Limite dépassée. Réessayez dans 1 minute.",
                    "requests_count": count
                }
            )

        response = await call_next(request)
        response.headers["X-RateLimit-Remaining"] = str(remaining)
        response.headers["X-RateLimit-Count"] = str(count)
        return response