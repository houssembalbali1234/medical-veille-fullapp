"""
app/kafka_consumer.py
=====================
Consumer Kafka — Pipeline IA automatique

Ce fichier est lance par docker-compose :
    python -m app.kafka_consumer

Role :
    Ecoute les topics Kafka publies par les scrapers (tasks.py)
    et declenche automatiquement la pipeline IA pour chaque
    nouvel article scrappe.

Flux automatique :
    scrape_pubmed() publie → article.scraped
        ↓ kafka_consumer recoit
    classify_article()     → specialite + type_etude
        ↓
    generate_resume_ia()   → resume Llama 3.1
        ↓
    vectorize_article()    → embedding Qdrant
        ↓
    index_article()        → indexation Elasticsearch
        ↓
    check_alerts()         → notifications utilisateurs

Sans ce consumer :
    - Le scraping fonctionne (articles sauvegardes dans MongoDB)
    - Mais la classification/resume/vectorisation doivent etre
      declenchees manuellement via les endpoints API

Avec ce consumer :
    - Tout est automatique apres chaque scraping
"""

import os
import json
import asyncio
import logging
from kafka import KafkaConsumer
from kafka.errors import KafkaError, NoBrokersAvailable

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | %(name)s | %(message)s"
)
logger = logging.getLogger("medical_veille.kafka_consumer")

# ============================================================
# CONFIGURATION
# ============================================================

KAFKA_URL    = os.getenv("KAFKA_URL", "kafka:29092")
MONGO_URL    = os.getenv("MONGO_URL", "mongodb://meduser:medpassword@mongodb:27017/medical_veille?authSource=admin")
ELASTIC_URL  = os.getenv("ELASTIC_URL", "http://elasticsearch:9200")
QDRANT_URL   = os.getenv("QDRANT_URL", "http://qdrant:6333")

# Topics a ecouter
TOPIC_ARTICLE_SCRAPED = "article.scraped"

# Retry config
MAX_RETRIES    = 5
RETRY_DELAY_S  = 10


# ============================================================
# PIPELINE IA — traitement d'un article
# ============================================================

async def process_new_article(pubmed_id: str, titre: str, keyword: str):
    """
    Declenche la pipeline IA complete pour un nouvel article.

    1. Recupere l'article depuis MongoDB
    2. Classification (specialite + type d'etude)
    3. Resume IA (Llama via Groq)
    4. Vectorisation (Qdrant)
    5. Indexation (Elasticsearch)
    6. Verification des alertes utilisateurs
    """
    logger.info(f"Pipeline IA demarre — pubmed_id={pubmed_id} titre='{titre[:50]}'")

    from pymongo import MongoClient
    client = MongoClient(MONGO_URL)
    db     = client["medical_veille"]

    try:
        # 1. Recuperer l'article depuis MongoDB
        article = db["articles"].find_one({"pubmed_id": pubmed_id})
        if not article:
            logger.warning(f"Article {pubmed_id} non trouve dans MongoDB")
            return

        article_dict = {
            "pubmed_id": article.get("pubmed_id", ""),
            "titre":     article.get("titre", ""),
            "resume":    article.get("resume", ""),
            "auteurs":   article.get("auteurs", []),
            "journal":   article.get("journal", ""),
            "annee":     article.get("annee", ""),
            "mots_cles": article.get("mots_cles", []),
        }

        # 2. Classification IA
        try:
            from app.services.classifier import classify_article
            classification = classify_article(article_dict)
            db["articles"].update_one(
                {"pubmed_id": pubmed_id},
                {"$set": {
                    "specialite": classification.get("specialite"),
                    "type_etude": classification.get("type_etude"),
                }}
            )
            logger.info(
                f"Classification OK — "
                f"specialite={classification.get('specialite')} "
                f"pubmed_id={pubmed_id}"
            )
            article_dict["specialite"] = classification.get("specialite")
            article_dict["type_etude"] = classification.get("type_etude")
        except Exception as e:
            logger.warning(f"Erreur classification {pubmed_id} : {e}")

        # 3. Resume IA (Llama via Groq)
        try:
            from app.services.llama_service import generate_resume_ia
            resume_result = generate_resume_ia(article_dict)
            db["articles"].update_one(
                {"pubmed_id": pubmed_id},
                {"$set": {
                    "resume_ia": resume_result.get("resume_ia"),
                    "resume_structure": {
                        "population":   resume_result.get("population"),
                        "intervention": resume_result.get("intervention"),
                        "resultats":    resume_result.get("resultats"),
                        "conclusion":   resume_result.get("conclusion"),
                    }
                }}
            )
            logger.info(f"Resume IA OK — {resume_result.get('mots', 0)} mots — {pubmed_id}")
        except Exception as e:
            logger.warning(f"Erreur resume IA {pubmed_id} : {e}")

        # 4. Vectorisation Qdrant
        try:
            from app.database.qdrant_database import vectorize_article
            article_for_qdrant = db["articles"].find_one(
                {"pubmed_id": pubmed_id},
                {"embedding": 0}
            )
            if article_for_qdrant:
                article_for_qdrant.pop("_id", None)
                success = await vectorize_article(article_for_qdrant)
                if success:
                    db["articles"].update_one(
                        {"pubmed_id": pubmed_id},
                        {"$set": {"est_vectorise": True}}
                    )
                    logger.info(f"Vectorisation Qdrant OK — {pubmed_id}")
        except Exception as e:
            logger.warning(f"Erreur vectorisation {pubmed_id} : {e}")

        # 5. Indexation Elasticsearch
        try:
            from app.database.elastic_database import index_article
            article_for_es = db["articles"].find_one(
                {"pubmed_id": pubmed_id},
                {"embedding": 0}
            )
            if article_for_es:
                article_for_es.pop("_id", None)
                await index_article(article_for_es)
                db["articles"].update_one(
                    {"pubmed_id": pubmed_id},
                    {"$set": {"est_indexe": True}}
                )
                logger.info(f"Indexation Elasticsearch OK — {pubmed_id}")
        except Exception as e:
            logger.warning(f"Erreur indexation {pubmed_id} : {e}")

        # 6. Verification des alertes utilisateurs
        try:
            from sqlalchemy.ext.asyncio import create_async_engine, async_sessionmaker
            from app.database.database import DATABASE_URL
            from app.services.alert_service import check_alerts_for_article

            final_article = db["articles"].find_one(
                {"pubmed_id": pubmed_id},
                {"pubmed_id": 1, "titre": 1, "resume": 1, "auteurs": 1}
            )
            if final_article:
                final_article.pop("_id", None)
                engine       = create_async_engine(DATABASE_URL)
                SessionLocal = async_sessionmaker(engine, expire_on_commit=False)
                async with SessionLocal() as session:
                    await check_alerts_for_article(final_article, session)
                await engine.dispose()
                logger.info(f"Alertes verifiees — {pubmed_id}")
        except Exception as e:
            logger.warning(f"Erreur verification alertes {pubmed_id} : {e}")

        logger.info(f"Pipeline IA terminee — {pubmed_id}")

    finally:
        client.close()


# ============================================================
# CONSUMER KAFKA — boucle principale
# ============================================================

def create_consumer() -> KafkaConsumer:
    """Cree et retourne un consumer Kafka avec retry."""
    for attempt in range(1, MAX_RETRIES + 1):
        try:
            consumer = KafkaConsumer(
                TOPIC_ARTICLE_SCRAPED,
                bootstrap_servers=[KAFKA_URL],
                value_deserializer=lambda v: json.loads(v.decode("utf-8")),
                group_id="medical_veille_pipeline",
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                auto_commit_interval_ms=5000,
                session_timeout_ms=30000,
                heartbeat_interval_ms=10000,
            )
            logger.info(f"Kafka Consumer connecte a {KAFKA_URL}")
            return consumer

        except NoBrokersAvailable:
            logger.warning(
                f"Kafka non disponible (tentative {attempt}/{MAX_RETRIES}). "
                f"Retry dans {RETRY_DELAY_S}s..."
            )
            if attempt < MAX_RETRIES:
                import time
                time.sleep(RETRY_DELAY_S)
            else:
                raise


async def run_consumer():
    """
    Boucle principale du consumer Kafka.
    Ecoute le topic article.scraped et declenche la pipeline IA.
    """
    logger.info("Demarrage du Kafka Consumer...")
    logger.info(f"Ecoute du topic : {TOPIC_ARTICLE_SCRAPED}")

    try:
        consumer = create_consumer()
    except NoBrokersAvailable:
        logger.error("Kafka inaccessible apres plusieurs tentatives. Arret.")
        return

    try:
        for message in consumer:
            try:
                event = message.value
                action    = event.get("action", "")
                pubmed_id = event.get("pubmed_id", "")
                titre     = event.get("titre", "")
                keyword   = event.get("keyword", "")

                logger.info(
                    f"Evenement recu — action={action} "
                    f"pubmed_id={pubmed_id} "
                    f"keyword='{keyword}'"
                )

                # Traiter uniquement les nouveaux articles scrapes
                if action == "scraped" and pubmed_id:
                    await process_new_article(
                        pubmed_id=pubmed_id,
                        titre=titre,
                        keyword=keyword
                    )

                elif action == "scraping_completed":
                    logger.info(
                        f"Scraping termine — keyword='{keyword}' "
                        f"nb_articles={event.get('nb_articles', 0)}"
                    )

            except Exception as e:
                logger.error(f"Erreur traitement message Kafka : {e}")
                continue

    except KeyboardInterrupt:
        logger.info("Arret demande par l'utilisateur")
    finally:
        consumer.close()
        logger.info("Kafka Consumer arrete proprement")


# ============================================================
# POINT D'ENTREE
# ============================================================

if __name__ == "__main__":
    asyncio.run(run_consumer())