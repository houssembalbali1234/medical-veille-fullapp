import os
from sqlalchemy.ext.asyncio import create_async_engine, AsyncSession, async_sessionmaker
from sqlalchemy.orm import declarative_base

# ===== POSTGRESQL UNIQUEMENT =====
# ✅ URL avec +asyncpg obligatoire pour le mode async
DATABASE_URL = os.getenv(
    "DATABASE_URL",
    "postgresql+asyncpg://meduser:medpassword@postgres:5432/medical_veille"
)

# ✅ Engine ASYNC — compatible avec FastAPI
# echo=False en production, mettre True pour déboguer les requêtes SQL
engine = create_async_engine(
    DATABASE_URL,
    echo=False,
    pool_size=10,        # ✅ nombre de connexions gardées ouvertes
    max_overflow=20,     # ✅ connexions supplémentaires si pool plein
    pool_pre_ping=True   # ✅ vérifie que la connexion est vivante avant utilisation
)

# ✅ Session ASYNC
AsyncSessionLocal = async_sessionmaker(
    engine,
    expire_on_commit=False  # ✅ évite les erreurs lazy loading après commit
)

Base = declarative_base()


# ✅ Dependency ASYNC pour FastAPI
# utilisée dans auth.py et routes avec Depends(get_db)
async def get_db() -> AsyncSession:
    async with AsyncSessionLocal() as session:
        try:
            yield session
            await session.commit()    # ✅ commit automatique si pas d'erreur
        except Exception:
            await session.rollback()  # ✅ rollback automatique si erreur
            raise