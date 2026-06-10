from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from contextlib import asynccontextmanager
from app.database.database import engine, Base
from app.database.mongo_database import create_mongo_indexes
from app.database.redis_database import init_redis, close_redis
from app.database.elastic_database import init_elasticsearch, close_elasticsearch
from app.database.qdrant_database import init_qdrant, close_qdrant
from app.database.kafka_producer import get_producer, close_producer
from app.middleware.rate_limit import RateLimitMiddleware
from app.auth import router as auth_router
from app.route.articles_mongo import router as articles_router
from app.route.articles import router as articles_pg_router
from app.route.recommendations import router as recommendations_router
from app.route.network import router as network_router
from app.route.alerts import router as alerts_router
from app.route.websocket import router as ws_router
from app.route.scispacy import router as scispacy_router
from app.tasks import scrape_pubmed, scrape_europe_pmc, scrape_biorxiv
import logging
from prometheus_fastapi_instrumentator import Instrumentator

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s",
    datefmt="%Y-%m-%d %H:%M:%S"
)
logger = logging.getLogger("medical_veille")


@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Demarrage de Medical Veille API...")

    try:
        async with engine.begin() as conn:
            await conn.run_sync(Base.metadata.create_all)
        logger.info("Tables PostgreSQL creees !")
    except Exception as e:
        logger.error(f"Erreur PostgreSQL : {e}")
        raise

    try:
        await create_mongo_indexes()
        logger.info("MongoDB pret !")
    except Exception as e:
        logger.error(f"Erreur MongoDB : {e}")
        raise

    try:
        await init_redis()
        logger.info("Redis pret !")
    except Exception as e:
        logger.error(f"Erreur Redis : {e}")
        raise

    try:
        await init_elasticsearch()
        logger.info("Elasticsearch pret !")
    except Exception as e:
        logger.error(f"Erreur Elasticsearch : {e}")
        raise

    try:
        await init_qdrant()
        logger.info("Qdrant + PubMedBert prets !")
    except Exception as e:
        logger.warning(f"Qdrant non disponible (ignore) : {e}")

    try:
        get_producer()
        logger.info("Kafka Producer pret !")
    except Exception as e:
        logger.warning(f"Kafka non disponible (ignore) : {e}")

    logger.info("Medical Veille API demarree avec succes !")
    yield

    logger.info("Arret de Medical Veille API...")
    await close_redis()
    await close_elasticsearch()
    try:
        await close_qdrant()
    except Exception as e:
        logger.warning(f"Erreur fermeture Qdrant : {e}")
    try:
        close_producer()
    except Exception as e:
        logger.warning(f"Erreur fermeture Kafka : {e}")
    logger.info("Arret propre termine.")


app = FastAPI(
    title="Medical Veille API",
    description="""
## Plateforme de veille scientifique medicale basee sur l IA

### Fonctionnalites
- Scraping automatique PubMed, Europe PMC, bioRxiv
- Classification IA par specialite medicale et type d etude
- Resumes intelligents via Llama 3.1 (Groq)
- Recherche full-text (Elasticsearch) + semantique (Qdrant)
- Feed personnalise par algorithme hybride
- Alertes temps reel via WebSocket + Socket.io
- Reseau de collaboration entre chercheurs
- Extraction entites medicales via scispaCy
    """,
    version="1.0.0",
    contact={"name": "Medical Veille Team"},
    lifespan=lifespan,
)

# ✅ Prometheus metrics
Instrumentator().instrument(app).expose(app)

# ============================================================
# MIDDLEWARES
# ============================================================

app.add_middleware(
    CORSMiddleware,
    allow_origins=[
        "http://localhost:3000", "http://localhost:3001",
        "http://127.0.0.1:3000", "http://127.0.0.1:3001",
    ],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.add_middleware(RateLimitMiddleware)

# ============================================================
# ROUTEURS
# ============================================================

app.include_router(auth_router)
app.include_router(articles_router)
app.include_router(articles_pg_router)
app.include_router(recommendations_router)
app.include_router(network_router)
app.include_router(alerts_router)
app.include_router(ws_router)
app.include_router(scispacy_router)

# ✅ Socket.io monté APRÈS les middlewares et routeurs
try:
    from app.route.socketio_route import socketio_app
    app.mount("/socket.io", socketio_app)
    logger.info("Socket.io monté sur /socket.io")
except Exception as e:
    logger.warning(f"Socket.io non disponible : {e}")

# ============================================================
# ROUTES DE BASE
# ============================================================

@app.get("/", tags=["Root"])
def root():
    return {
        "message": "Medical Veille Backend Running",
        "version": "1.0.0",
        "docs":    "/docs",
        "redoc":   "/redoc",
        "health":  "/health",
    }


@app.get("/health", tags=["Root"])
async def health():
    from app.database.redis_database import redis_client
    from app.database.mongo_database import mongo_client

    services = {}

    try:
        await redis_client.ping()
        services["redis"] = "ok"
    except Exception:
        services["redis"] = "error"

    try:
        await mongo_client.admin.command("ping")
        services["mongodb"] = "ok"
    except Exception:
        services["mongodb"] = "error"

    all_ok = all(v == "ok" for v in services.values())

    return {
        "status":   "ok" if all_ok else "degraded",
        "version":  "1.0.0",
        "services": services,
    }


@app.post("/scrape/{keyword}", tags=["Scraping"])
def scrape(keyword: str, max_results: int = 20):
    task = scrape_pubmed.delay(keyword, max_results)
    return {
        "task_id":      task.id,
        "status":       "Scraping lance !",
        "keyword":      keyword,
        "max_results":  max_results,
        "check_status": f"/task/{task.id}",
    }


@app.post("/scrape/europe-pmc/{keyword}", tags=["Scraping"])
def scrape_epmc(keyword: str, max_results: int = 20):
    task = scrape_europe_pmc.delay(keyword, max_results)
    return {
        "task_id":      task.id,
        "status":       "Scraping Europe PMC lance !",
        "keyword":      keyword,
        "max_results":  max_results,
        "check_status": f"/task/{task.id}",
    }


@app.post("/scrape/biorxiv/{keyword}", tags=["Scraping"])
def scrape_biorxiv_endpoint(keyword: str, max_results: int = 20):
    task = scrape_biorxiv.delay(keyword, max_results)
    return {
        "task_id":      task.id,
        "status":       "Scraping bioRxiv lance !",
        "keyword":      keyword,
        "max_results":  max_results,
        "check_status": f"/task/{task.id}",
    }


@app.get("/task/{task_id}", tags=["Scraping"])
def get_task_status(task_id: str):
    from celery.result import AsyncResult
    from app.tasks import celery
    result = AsyncResult(task_id, app=celery)
    return {
        "task_id":    task_id,
        "status":     result.status,
        "result":     result.result if result.ready() else None,
        "ready":      result.ready(),
        "successful": result.successful() if result.ready() else None,
    }