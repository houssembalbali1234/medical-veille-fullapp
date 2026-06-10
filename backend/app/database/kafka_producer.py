import os
import json
from datetime import datetime
from typing import Optional
from kafka import KafkaProducer
from kafka.errors import KafkaError

# ============================================================
# ⚙️ CONFIGURATION
# ============================================================

KAFKA_URL = os.getenv("KAFKA_URL", "kafka:29092")

# Topics Kafka — chaque topic = un type d'événement
TOPIC_ARTICLE_SCRAPED = "article.scraped"      # Nouvel article scraped
TOPIC_ARTICLE_INDEXED = "article.indexed"      # Article indexé dans ES
TOPIC_ARTICLE_VECTORIZED = "article.vectorized" # Article vectorisé dans Qdrant

# Producer global
_producer: Optional[KafkaProducer] = None


# ============================================================
# 🚀 INITIALISATION
# ============================================================

def get_producer() -> KafkaProducer:
    """
    Retourne le producer Kafka (singleton).
    
    KafkaProducer = l'objet qui envoie des messages dans Kafka.
    On utilise un singleton pour ne pas créer une nouvelle connexion
    à chaque message envoyé.
    """
    global _producer
    if _producer is None:
        _producer = KafkaProducer(
            bootstrap_servers=[KAFKA_URL],
            value_serializer=lambda v: json.dumps(v, default=str).encode("utf-8"),
            key_serializer=lambda k: k.encode("utf-8") if k else None,
            retries=3,
            acks="all"  # Attendre confirmation de réception
        )
        print(f"✅ Kafka Producer connecté à {KAFKA_URL} !")
    return _producer


def close_producer():
    """Ferme le producer Kafka proprement"""
    global _producer
    if _producer:
        _producer.flush()
        _producer.close()
        _producer = None
        print("🔴 Kafka Producer déconnecté.")


# ============================================================
# 📤 ENVOI DE MESSAGES
# ============================================================

def publish_article_scraped(pubmed_id: str, keyword: str, titre: str):
    """
    Publie un événement 'article.scraped' dans Kafka.
    
    Pourquoi Kafka ici ?
    Quand Celery scrape un article et le sauvegarde dans MongoDB,
    il publie un événement dans Kafka.
    Le consumer Kafka (dans le backend) reçoit cet événement et
    déclenche automatiquement l'indexation ES + vectorisation Qdrant.
    
    Sans Kafka → tu dois lancer /index-all et /vectorize-all manuellement
    Avec Kafka → tout est automatique ! 🎯
    """
    try:
        producer = get_producer()
        message = {
            "pubmed_id": pubmed_id,
            "keyword": keyword,
            "titre": titre,
            "timestamp": datetime.utcnow().isoformat(),
            "action": "scraped"
        }
        producer.send(
            topic=TOPIC_ARTICLE_SCRAPED,
            key=pubmed_id,
            value=message
        )
        producer.flush()
        print(f"📤 Kafka: article.scraped publié → {pubmed_id}")
    except KafkaError as e:
        print(f"⚠️ Kafka error (publish_article_scraped): {e}")
    except Exception as e:
        print(f"⚠️ Erreur inattendue Kafka: {e}")


def publish_article_indexed(pubmed_id: str):
    """Publie un événement 'article.indexed' dans Kafka"""
    try:
        producer = get_producer()
        message = {
            "pubmed_id": pubmed_id,
            "timestamp": datetime.utcnow().isoformat(),
            "action": "indexed"
        }
        producer.send(
            topic=TOPIC_ARTICLE_INDEXED,
            key=pubmed_id,
            value=message
        )
        producer.flush()
        print(f"📤 Kafka: article.indexed publié → {pubmed_id}")
    except KafkaError as e:
        print(f"⚠️ Kafka error (publish_article_indexed): {e}")
    except Exception as e:
        print(f"⚠️ Erreur inattendue Kafka: {e}")


def publish_article_vectorized(pubmed_id: str):
    """Publie un événement 'article.vectorized' dans Kafka"""
    try:
        producer = get_producer()
        message = {
            "pubmed_id": pubmed_id,
            "timestamp": datetime.utcnow().isoformat(),
            "action": "vectorized"
        }
        producer.send(
            topic=TOPIC_ARTICLE_VECTORIZED,
            key=pubmed_id,
            value=message
        )
        producer.flush()
        print(f"📤 Kafka: article.vectorized publié → {pubmed_id}")
    except KafkaError as e:
        print(f"⚠️ Kafka error (publish_article_vectorized): {e}")
    except Exception as e:
        print(f"⚠️ Erreur inattendue Kafka: {e}")


def publish_scraping_completed(keyword: str, nb_articles: int):
    """
    Publie un événement 'scraping.completed' dans Kafka.
    Déclenche l'indexation automatique de tous les nouveaux articles.
    """
    try:
        producer = get_producer()
        message = {
            "keyword": keyword,
            "nb_articles": nb_articles,
            "timestamp": datetime.utcnow().isoformat(),
            "action": "scraping_completed"
        }
        producer.send(
            topic=TOPIC_ARTICLE_SCRAPED,
            key=keyword,
            value=message
        )
        producer.flush()
        print(f"📤 Kafka: scraping.completed publié → {keyword} ({nb_articles} articles)")
    except KafkaError as e:
        print(f"⚠️ Kafka error (publish_scraping_completed): {e}")
    except Exception as e:
        print(f"⚠️ Erreur inattendue Kafka: {e}")