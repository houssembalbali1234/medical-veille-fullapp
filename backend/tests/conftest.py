"""
conftest.py — Configuration des tests pytest
"""

import pytest
import asyncio
from httpx import AsyncClient, ASGITransport

import os
os.environ.setdefault("SECRET_KEY", "test-secret-key-ci")
os.environ.setdefault("DATABASE_URL", "postgresql+asyncpg://meduser:medpassword@localhost:5432/medical_veille_test")
os.environ.setdefault("MONGO_URL", "mongodb://meduser:medpassword@localhost:27017/medical_veille_test?authSource=admin")
os.environ.setdefault("REDIS_URL", "redis://localhost:6379/0")
os.environ.setdefault("ELASTICSEARCH_URL", "http://localhost:9200")
os.environ.setdefault("QDRANT_URL", "http://localhost:6333")
os.environ.setdefault("RABBITMQ_URL", "amqp://guest:guest@localhost:5672//")
os.environ.setdefault("GROQ_API_KEY", "test-groq-key")

from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
from sqlalchemy.pool import NullPool
from app.database.database import Base, get_db
from app.main import app

TEST_DATABASE_URL = os.environ["DATABASE_URL"]

engine_test = create_async_engine(
    TEST_DATABASE_URL,
    poolclass=NullPool,
    echo=False,
)

TestSessionLocal = async_sessionmaker(
    engine_test,
    expire_on_commit=False,
    autoflush=False,
)


@pytest.fixture(scope="session")
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()


@pytest.fixture(scope="session", autouse=True)
async def setup_services():
    """Initialise les services nécessaires aux tests."""
    # Créer les tables PostgreSQL
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Initialiser Redis — nécessaire pour le RateLimitMiddleware
    from app.database.redis_database import init_redis, close_redis
    await init_redis()

    yield

    # Cleanup
    await close_redis()
    async with engine_test.begin() as conn:
        await conn.run_sync(Base.metadata.drop_all)


@pytest.fixture
async def db_session():
    async with TestSessionLocal() as session:
        yield session
        await session.rollback()


@pytest.fixture
async def client(db_session):
    async def override_get_db():
        yield db_session

    app.dependency_overrides[get_db] = override_get_db

    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://test"
    ) as ac:
        yield ac

    app.dependency_overrides.clear()


@pytest.fixture
async def auth_token(client):
    await client.post("/auth/register", json={
        "username": "testuser",
        "email": "test@medveille.com",
        "password": "testpassword123"
    })
    response = await client.post("/auth/login", json={
        "email": "test@medveille.com",
        "password": "testpassword123"
    })
    return response.json()["access_token"]


@pytest.fixture
def auth_headers(auth_token):
    return {"Authorization": f"Bearer {auth_token}"}