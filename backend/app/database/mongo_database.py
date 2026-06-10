from motor.motor_asyncio import AsyncIOMotorClient
import os

# ✅ CORRECTION 1 — Suppression du client sync ici
# Le client sync appartient uniquement à tasks.py (Celery worker)
# Charger pymongo ici créait une connexion inutile côté FastAPI

MONGO_URL = os.getenv(
    "MONGO_URL",
    "mongodb://meduser:medpassword@mongodb:27017/medical_veille?authSource=admin"
)

# ✅ Client ASYNC uniquement (pour FastAPI)
mongo_client = AsyncIOMotorClient(MONGO_URL)
mongo_db = mongo_client["medical_veille"]

# Collections async
articles_collection = mongo_db["articles"]
scraping_logs_collection = mongo_db["scraping_logs"]


async def get_mongo_db():
    """Dependency FastAPI pour obtenir la base MongoDB"""
    return mongo_db


async def create_mongo_indexes():
    """Créer les index MongoDB pour optimiser les recherches"""

    # ✅ Index unique sur pubmed_id pour éviter les doublons
    await articles_collection.create_index(
        "pubmed_id",
        unique=True,
        sparse=True  # sparse=True ignore les documents sans pubmed_id
    )

    # ✅ Index sur specialite pour filtrer rapidement par spécialité
    await articles_collection.create_index("specialite")

    # ✅ Index sur type_etude (RCT, meta-analyse...) — prévu dans cahier des charges
    await articles_collection.create_index("type_etude")

    # ✅ Index sur source (pubmed, europe_pmc, biorxiv)
    await articles_collection.create_index("source")

    # ✅ Index sur annee pour trier et filtrer par année
    await articles_collection.create_index("annee")

    # ✅ Index sur keyword_recherche pour retrouver les articles par mot-clé de scraping
    await articles_collection.create_index("keyword_recherche")

    # ✅ Index sur est_vectorise et est_indexe
    # Très utile pour le pipeline IA — retrouver rapidement
    # les articles non encore traités par Qdrant ou Elasticsearch
    await articles_collection.create_index("est_vectorise")
    await articles_collection.create_index("est_indexe")

    # ✅ Index sur scraped_at pour trier par date de scraping (utilisé dans GET /)
    await articles_collection.create_index("scraped_at")

    # ✅ Index textuel pour recherche full-text basique (MongoDB $text)
    # En attendant l'intégration Elasticsearch (cahier des charges)
    await articles_collection.create_index([
        ("titre", "text"),
        ("resume", "text"),
        ("mots_cles", "text"),
        ("mesh_terms", "text")   # ✅ AJOUT — mesh_terms utile pour recherche médicale
    ])

    # ✅ Index sur les logs de scraping
    await scraping_logs_collection.create_index("keyword")
    await scraping_logs_collection.create_index("statut")
    await scraping_logs_collection.create_index(
        "debut",
        name="debut_desc"
    )

    print("✅ Index MongoDB créés !")