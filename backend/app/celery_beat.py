"""
celery_beat.py — Planificateur automatique des tâches périodiques

Pourquoi ce fichier existe ?
==============================
Dans tasks.py, le scraping est déclenché MANUELLEMENT via un POST HTTP.
Le cahier des charges impose un scraping QUOTIDIEN automatique.
Celery Beat est le "cron" de Celery : il déclenche des tâches selon un calendrier.

Comment ça marche ?
===================
1. Ce fichier configure l'app Celery avec les schedules
2. On lance un worker Celery Beat séparé dans Docker
3. Il déclenche les tâches selon le calendrier, sans intervention humaine

Pour lancer Celery Beat (dans Docker ou terminal) :
    celery -A app.celery_beat beat --loglevel=info

Pour lancer le worker qui exécute les tâches :
    celery -A app.celery_beat worker --loglevel=info

Ou les deux en même temps (dev uniquement) :
    celery -A app.celery_beat worker --beat --loglevel=info
"""

import os
from celery import Celery
from celery.schedules import crontab

# ============================================================
# ⚙️ CONFIGURATION CELERY
# ============================================================

REDIS_URL = os.getenv("REDIS_URL", "redis://redis:6379/0")

# 🐇 RabbitMQ = broker (file de messages des tâches)
# 🔴 Redis    = backend (stockage des résultats — DB 1 séparée du cache DB 0)
RABBITMQ_URL = os.getenv(
    "CELERY_BROKER_URL",
    os.getenv("RABBITMQ_URL", "amqp://meduser:medpassword@rabbitmq:5672//")  # ✅ vhost "/"
)
REDIS_BACKEND_URL = os.getenv(
    "CELERY_RESULT_BACKEND",
    REDIS_URL.replace("/0", "/1")  # DB 1 pour les résultats, DB 0 pour le cache
)

celery_app = Celery(
    "medical_veille",
    broker=RABBITMQ_URL,
    backend=REDIS_BACKEND_URL,
    include=["app.tasks"],  # ✅ seul module existant
)

# ============================================================
# ⚙️ CONFIGURATION GLOBALE CELERY
# ============================================================

celery_app.conf.update(
    # Fuseau horaire — important pour les cron !
    timezone="Europe/Paris",
    enable_utc=True,

    # Sérialisation JSON (plus sûr que pickle)
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],

    # Résultats expirés après 24h (évite d'encombrer Redis)
    result_expires=86400,

    # Retry automatique si le broker est indisponible au démarrage
    broker_connection_retry_on_startup=True,

    # Prefetch : chaque worker prend 1 tâche à la fois (évite les blocages)
    worker_prefetch_multiplier=1,

    # Timeout tâches longues (scraping, vectorisation)
    task_time_limit=600,      # Kill après 10 min
    task_soft_time_limit=540, # Warning à 9 min
)

# ============================================================
# 📅 SCHEDULE DES TÂCHES PÉRIODIQUES
# ============================================================

celery_app.conf.beat_schedule = {

    # ----------------------------------------------------------
    # 🔬 SCRAPING QUOTIDIEN — PubMed (6h00 → 6h50)
    # Espacé de 10 min pour ne pas surcharger l'API Entrez
    # ----------------------------------------------------------
    "scraping-pubmed-cardio-quotidien": {
        "task": "app.tasks.scrape_pubmed",
        "schedule": crontab(hour=6, minute=0),
        "args": ("cardiology heart disease", 50),
        "options": {"queue": "scraping"},
    },
    "scraping-pubmed-oncologie-quotidien": {
        "task": "app.tasks.scrape_pubmed",
        "schedule": crontab(hour=6, minute=10),
        "args": ("cancer oncology treatment", 50),
        "options": {"queue": "scraping"},
    },
    "scraping-pubmed-diabete-quotidien": {
        "task": "app.tasks.scrape_pubmed",
        "schedule": crontab(hour=6, minute=20),
        "args": ("diabetes mellitus insulin", 50),
        "options": {"queue": "scraping"},
    },
    "scraping-pubmed-neurologie-quotidien": {
        "task": "app.tasks.scrape_pubmed",
        "schedule": crontab(hour=6, minute=30),
        "args": ("neurology alzheimer parkinson", 50),
        "options": {"queue": "scraping"},
    },
    "scraping-pubmed-infectio-quotidien": {
        "task": "app.tasks.scrape_pubmed",
        "schedule": crontab(hour=6, minute=40),
        "args": ("infectious disease antibiotic", 50),
        "options": {"queue": "scraping"},
    },

    # ----------------------------------------------------------
    # 🌍 SCRAPING QUOTIDIEN — Europe PMC (7h00)
    # Décalé d'1h pour ne pas surcharger en même temps que PubMed
    # ----------------------------------------------------------
    "scraping-europepmc-quotidien": {
        "task": "app.tasks.scrape_europe_pmc",
        "schedule": crontab(hour=7, minute=0),
        "args": ("clinical trial randomized controlled", 50),
        "options": {"queue": "scraping"},
    },

    # ----------------------------------------------------------
    # 📄 SCRAPING QUOTIDIEN — bioRxiv (7h30)
    # ----------------------------------------------------------
    "scraping-biorxiv-quotidien": {
        "task": "app.tasks.scrape_biorxiv",
        "schedule": crontab(hour=7, minute=30),
        "args": ("medicine biology", 30),
        "options": {"queue": "scraping"},
    },

    # ----------------------------------------------------------
    # 🧠 CLASSIFICATION IA — après scraping (10h00)
    # Spécialité + type d'étude via PubMedBert (Zero-Shot)
    # ----------------------------------------------------------
    "classification-articles-quotidien": {
        "task": "app.celery_beat.scheduled_classify_articles",
        "schedule": crontab(hour=10, minute=0),
        "options": {"queue": "ai"},
    },

    # ----------------------------------------------------------
    # 📝 RÉSUMÉS IA — Llama 3.1 via Groq (11h00)
    # Limité à 50 articles/jour pour respecter les quotas Groq
    # ----------------------------------------------------------
    "resumes-ia-quotidien": {
        "task": "app.celery_beat.scheduled_generate_resumes",
        "schedule": crontab(hour=11, minute=0),
        "args": (50,),
        "options": {"queue": "ai"},
    },

    # ----------------------------------------------------------
    # 🔍 INDEXATION Elasticsearch + Qdrant (12h00 / 12h30)
    # ----------------------------------------------------------
    "indexation-elasticsearch-quotidien": {
        "task": "app.celery_beat.scheduled_index_articles",
        "schedule": crontab(hour=12, minute=0),
        "options": {"queue": "indexing"},
    },
    "vectorisation-qdrant-quotidien": {
        "task": "app.celery_beat.scheduled_vectorize_articles",
        "schedule": crontab(hour=12, minute=30),
        "options": {"queue": "indexing"},
    },

    # ----------------------------------------------------------
    # 🔔 VÉRIFICATION ALERTES — après indexation (13h00)
    # Mots-clés + auteurs suivis → notifications + push WebSocket
    # ----------------------------------------------------------
    "verif-alertes-quotidien": {
        "task": "app.celery_beat.scheduled_check_alerts",
        "schedule": crontab(hour=13, minute=0),
        "options": {"queue": "notifications"},
    },

    # ----------------------------------------------------------
    # 📬 DIGEST HEBDOMADAIRE — chaque lundi à 8h00
    # ----------------------------------------------------------
    "digest-hebdomadaire-lundi": {
        "task": "app.celery_beat.scheduled_weekly_digest",
        "schedule": crontab(hour=8, minute=0, day_of_week=1),
        "options": {"queue": "notifications"},
    },

    # ----------------------------------------------------------
    # 🧹 NETTOYAGE — chaque dimanche à 2h00
    # Supprime les logs anciens et résultats Celery expirés
    # ----------------------------------------------------------
    "nettoyage-hebdomadaire": {
        "task": "app.celery_beat.scheduled_cleanup",
        "schedule": crontab(hour=2, minute=0, day_of_week=0),
        "options": {"queue": "maintenance"},
    },
}


# ============================================================
# 🧠 TÂCHES PIPELINE IA
# ============================================================

@celery_app.task(name="app.celery_beat.scheduled_classify_articles")
def scheduled_classify_articles():
    """Classification IA — spécialité + type d'étude (PubMedBert Zero-Shot)."""
    import asyncio
    from app.services.classifier import classify_all_articles
    result = asyncio.run(classify_all_articles())
    return result


@celery_app.task(name="app.celery_beat.scheduled_generate_resumes")
def scheduled_generate_resumes(limit: int = 50):
    """Résumés IA — Llama 3.1 via Groq (limité pour respecter les quotas)."""
    import asyncio
    from app.services.llama_service import generate_resumes_bulk
    result = asyncio.run(generate_resumes_bulk(limit=limit))
    return result


@celery_app.task(name="app.celery_beat.scheduled_index_articles")
def scheduled_index_articles():
    """Indexation Elasticsearch — appelle l'API interne."""
    import asyncio
    import httpx

    api_url = os.getenv("API_INTERNAL_URL", "http://api:8000")

    async def _run():
        async with httpx.AsyncClient(base_url=api_url, timeout=300) as client:
            resp = await client.post("/articles/index-all")
            resp.raise_for_status()
            return resp.json()

    return asyncio.run(_run())


@celery_app.task(name="app.celery_beat.scheduled_vectorize_articles")
def scheduled_vectorize_articles():
    """Vectorisation Qdrant — appelle l'API interne."""
    import asyncio
    import httpx

    api_url = os.getenv("API_INTERNAL_URL", "http://api:8000")

    async def _run():
        async with httpx.AsyncClient(base_url=api_url, timeout=300) as client:
            resp = await client.post("/articles/vectorize-all")
            resp.raise_for_status()
            return resp.json()

    return asyncio.run(_run())


# ============================================================
# 🔔 ALERTES
# ============================================================

@celery_app.task(name="app.celery_beat.scheduled_check_alerts")
def scheduled_check_alerts():
    """
    Vérifie les alertes pour les articles du jour.
    Notification PostgreSQL + push WebSocket pour chaque match.
    """
    import asyncio
    from pymongo import MongoClient
    from datetime import datetime, timedelta

    async def _run():
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from app.database.database import DATABASE_URL
        from app.services.alert_service import check_alerts_for_article

        engine       = create_async_engine(DATABASE_URL)
        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

        mongo_client = MongoClient(os.getenv(
            "MONGO_URL",
            "mongodb://meduser:medpassword@mongodb:27017/medical_veille?authSource=admin"
        ))
        articles = list(
            mongo_client["medical_veille"]["articles"].find(
                {"scraped_at": {"$gte": datetime.utcnow() - timedelta(hours=24)}},
                {"pubmed_id": 1, "titre": 1, "resume": 1, "auteurs": 1}
            )
        )
        mongo_client.close()

        if not articles:
            return {"checked": 0}

        nb_checked = 0
        async with SessionLocal() as session:
            for article in articles:
                article.pop("_id", None)
                await check_alerts_for_article(article, session)
                nb_checked += 1

        await engine.dispose()
        return {"checked": nb_checked}

    return asyncio.run(_run())


# ============================================================
# 📧 DIGEST HEBDOMADAIRE
# ============================================================

@celery_app.task(name="app.celery_beat.scheduled_weekly_digest")
def scheduled_weekly_digest():
    """
    Envoie le digest hebdomadaire à tous les utilisateurs actifs.
    Ignoré si l'utilisateur n'a aucun article cette semaine.
    """
    import asyncio

    async def _run():
        from sqlalchemy import select
        from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
        from app.database.database import DATABASE_URL
        from app.models import User
        from app.services.alert_service import generate_weekly_digest
        from app.services.email_service import send_weekly_digest

        engine       = create_async_engine(DATABASE_URL)
        SessionLocal = async_sessionmaker(engine, expire_on_commit=False)

        nb_sent = nb_skipped = nb_errors = 0

        async with SessionLocal() as session:
            result = await session.execute(select(User).where(User.is_active == True))
            users  = result.scalars().all()

            for user in users:
                try:
                    digest = await generate_weekly_digest(str(user.id), session)

                    if digest.get("nb_articles", 0) == 0:
                        nb_skipped += 1
                        continue

                    sent = await send_weekly_digest(
                        to_email=user.email,
                        username=user.username,
                        specialites=digest.get("specialites_suivies", []),
                        articles=digest.get("articles", []),
                    )
                    nb_sent += 1 if sent else 0
                    nb_errors += 0 if sent else 1

                except Exception as e:
                    nb_errors += 1

        await engine.dispose()
        return {"sent": nb_sent, "skipped": nb_skipped, "errors": nb_errors, "total": len(users)}

    return asyncio.run(_run())


# ============================================================
# 🧹 NETTOYAGE
# ============================================================

@celery_app.task(name="app.celery_beat.scheduled_cleanup")
def scheduled_cleanup():
    """
    Nettoyage hebdomadaire — chaque dimanche à 2h.
    Supprime les logs de scraping de plus de 30 jours.
    """
    from pymongo import MongoClient
    from datetime import datetime, timedelta

    mongo_client = MongoClient(os.getenv(
        "MONGO_URL",
        "mongodb://meduser:medpassword@mongodb:27017/medical_veille?authSource=admin"
    ))
    result = mongo_client["medical_veille"]["scraping_logs"].delete_many(
        {"debut": {"$lt": datetime.utcnow() - timedelta(days=30)}}
    )
    mongo_client.close()

    return {
        "deleted_logs": result.deleted_count,
        "cleaned_at":   datetime.utcnow().isoformat(),
    }