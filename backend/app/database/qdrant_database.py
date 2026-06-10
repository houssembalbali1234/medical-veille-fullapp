import os
from typing import Optional
from qdrant_client import AsyncQdrantClient
from qdrant_client.models import (
    Distance,
    VectorParams,
    PointStruct,
    Filter,
    FieldCondition,
    MatchValue,
    SearchRequest
)
from sentence_transformers import SentenceTransformer

# ============================================================
# ⚙️ CONFIGURATION
# ============================================================

QDRANT_URL = os.getenv("QDRANT_URL", "http://qdrant:6333")
COLLECTION_NAME = "articles_medicaux"
VECTOR_SIZE = 768  # S-PubMedBert produit des vecteurs de 768 dimensions
MODEL_NAME = "pritamdeka/S-PubMedBert-MS-MARCO"

# Clients globaux
qdrant_client: Optional[AsyncQdrantClient] = None
embedding_model: Optional[SentenceTransformer] = None


# ============================================================
# 🚀 INITIALISATION
# ============================================================

async def init_qdrant():
    """
    Initialise Qdrant et charge le modèle d'embeddings au démarrage.

    Que fait cette fonction ?
    1. Connecte au serveur Qdrant (dans Docker)
    2. Charge le modèle S-PubMedBert depuis HuggingFace (1ère fois: télécharge ~400MB)
    3. Crée la collection 'articles_medicaux' si elle n'existe pas
    """
    global qdrant_client, embedding_model

    # 1. Connexion à Qdrant
    qdrant_client = AsyncQdrantClient(url=QDRANT_URL)
    print(f"✅ Qdrant connecté à {QDRANT_URL} !")

    # 2. Charger le modèle d'embeddings médical
    print(f"⏳ Chargement du modèle {MODEL_NAME} (peut prendre 1-2 min la première fois)...")
    embedding_model = SentenceTransformer(MODEL_NAME)
    print(f"✅ Modèle {MODEL_NAME} chargé !")

    # 3. Créer la collection si elle n'existe pas
    await create_collection()


async def close_qdrant():
    """Ferme la connexion Qdrant proprement à l'arrêt de l'app"""
    global qdrant_client
    if qdrant_client:
        await qdrant_client.close()
        print("🔴 Qdrant déconnecté.")


# ============================================================
# 📦 COLLECTION
# ============================================================

async def create_collection():
    """
    Crée la collection Qdrant pour les articles médicaux.

    Une collection Qdrant = une table, mais pour les vecteurs.
    On définit :
    - La taille des vecteurs (768 pour PubMedBert)
    - La métrique de distance (Cosine = meilleure pour le texte)

    Distance Cosine : mesure l'angle entre deux vecteurs.
    Si angle = 0° → articles identiques (score = 1.0)
    Si angle = 90° → articles sans rapport (score = 0.0)
    """
    collections = await qdrant_client.get_collections()
    existing = [c.name for c in collections.collections]

    if COLLECTION_NAME in existing:
        print(f"✅ Collection '{COLLECTION_NAME}' déjà existante.")
        return

    await qdrant_client.create_collection(
        collection_name=COLLECTION_NAME,
        vectors_config=VectorParams(
            size=VECTOR_SIZE,        # 768 dimensions
            distance=Distance.COSINE # Similarité cosinus
        )
    )
    print(f"✅ Collection '{COLLECTION_NAME}' créée avec {VECTOR_SIZE} dimensions !")


# ============================================================
# 🔢 VECTORISATION (Embedding)
# ============================================================

def get_embedding(text: str) -> list[float]:
    """
    Convertit un texte en vecteur de 768 nombres (embedding).

    Comment ça marche ?
    Le modèle S-PubMedBert lit le texte et produit 768 nombres
    qui représentent le "sens médical" du texte.

    Exemple :
    "diabetes treatment" → [0.12, -0.45, 0.78, ..., 0.33]  (768 valeurs)
    "insulin therapy"    → [0.11, -0.44, 0.76, ..., 0.31]  (768 valeurs)
    Ces deux vecteurs seront très proches car les textes sont similaires !

    On combine titre + résumé pour avoir le contexte complet.
    """
    return embedding_model.encode(text, normalize_embeddings=True).tolist()


def build_article_text(article: dict) -> str:
    """
    Construit le texte à vectoriser depuis un article.
    On combine titre + résumé + mots-clés pour maximiser la précision.
    """
    parts = []
    if article.get("titre"):
        parts.append(article["titre"])
    if article.get("resume"):
        parts.append(article["resume"])
    if article.get("mots_cles"):
        mots = article["mots_cles"]
        if isinstance(mots, list):
            parts.append(" ".join(mots))
    return " ".join(parts)


# ============================================================
# 📥 VECTORISATION DES ARTICLES
# ============================================================

async def vectorize_article(article: dict) -> bool:
    """
    Vectorise un seul article et le stocke dans Qdrant.

    Processus :
    1. Construit le texte (titre + résumé + mots-clés)
    2. Génère le vecteur de 768 dimensions
    3. Stocke dans Qdrant avec les métadonnées de l'article

    Le 'payload' = les métadonnées stockées avec le vecteur
    (pour pouvoir afficher les infos sans aller chercher dans MongoDB)
    """
    pubmed_id = article.get("pubmed_id")
    if not pubmed_id:
        return False

    # 1. Construire le texte et générer l'embedding
    text = build_article_text(article)
    if not text.strip():
        return False

    vector = get_embedding(text)

    # 2. Créer le point Qdrant
    # ID numérique requis par Qdrant — on utilise le hash du pubmed_id
    point_id = abs(hash(pubmed_id)) % (2**53)

    point = PointStruct(
        id=point_id,
        vector=vector,
        payload={
            "pubmed_id": pubmed_id,
            "titre": article.get("titre", ""),
            "journal": article.get("journal", ""),
            "specialite": article.get("specialite"),
            "mots_cles": article.get("mots_cles", []),
            "score_pertinence": article.get("score_pertinence", 0),
        }
    )

    # 3. Stocker dans Qdrant
    await qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=[point]
    )
    return True


async def vectorize_articles_bulk(articles: list[dict]) -> int:
    """
    Vectorise plusieurs articles en une seule opération.

    Optimisation : on génère tous les embeddings en batch
    (plus rapide que un par un car le modèle traite plusieurs textes en parallèle)
    """
    if not articles:
        return 0

    # 1. Construire tous les textes
    texts = [build_article_text(a) for a in articles]

    # 2. Générer tous les embeddings en batch (plus rapide !)
    print(f"⏳ Vectorisation de {len(articles)} articles...")
    vectors = embedding_model.encode(
        texts,
        normalize_embeddings=True,
        batch_size=32,          # Traiter 32 articles à la fois
        show_progress_bar=True  # Affiche une barre de progression
    ).tolist()

    # 3. Créer les points Qdrant
    points = []
    for article, vector in zip(articles, vectors):
        pubmed_id = article.get("pubmed_id")
        if not pubmed_id:
            continue
        point_id = abs(hash(pubmed_id)) % (2**53)
        points.append(PointStruct(
            id=point_id,
            vector=vector,
            payload={
                "pubmed_id": pubmed_id,
                "titre": article.get("titre", ""),
                "journal": article.get("journal", ""),
                "specialite": article.get("specialite"),
                "mots_cles": article.get("mots_cles", []),
                "score_pertinence": article.get("score_pertinence", 0),
            }
        ))

    # 4. Stocker en bulk dans Qdrant
    await qdrant_client.upsert(
        collection_name=COLLECTION_NAME,
        points=points
    )

    print(f"✅ {len(points)} articles vectorisés dans Qdrant !")
    return len(points)


# ============================================================
# 🔍 RECHERCHE SÉMANTIQUE
# ============================================================

async def search_similar(
    query: str,
    specialite: Optional[str] = None,
    limit: int = 10,
    score_threshold: float = 0.3
) -> list[dict]:
    """
    Recherche sémantique : trouve les articles les plus similaires à la requête.

    Comment ça marche ?
    1. On vectorise la requête (ex: "kidney disease treatment")
    2. Qdrant compare ce vecteur avec tous les vecteurs stockés
    3. Retourne les articles dont le vecteur est le plus proche

    score_threshold = 0.3 : seuil minimum de similarité
    (0.0 = pas similaire du tout, 1.0 = identique)

    Avantage vs Elasticsearch :
    - Elasticsearch cherche les MOTS exacts
    - Qdrant cherche le SENS → trouve "renal failure" quand on cherche "kidney disease"

    ✅ Utilise search() compatible avec Qdrant v1.9.0
    """
    # 1. Vectoriser la requête
    query_vector = get_embedding(query)

    # 2. Construire le filtre optionnel par spécialité
    search_filter = None
    if specialite:
        search_filter = Filter(
            must=[
                FieldCondition(
                    key="specialite",
                    match=MatchValue(value=specialite)
                )
            ]
        )

    # 3. ✅ Rechercher avec search() — compatible Qdrant v1.9.0
    # query_points() nécessite Qdrant v1.10+ — on utilise search() à la place
    results = await qdrant_client.search(
        collection_name=COLLECTION_NAME,
        query_vector=query_vector,
        query_filter=search_filter,
        limit=limit,
        score_threshold=score_threshold,
        with_payload=True,
        with_vectors=False
    )

    # 4. Formater les résultats
    articles = []
    for hit in results:
        article = hit.payload
        article["similarity_score"] = round(hit.score, 4)
        articles.append(article)

    return articles


async def get_qdrant_stats() -> dict:
    """Statistiques de la collection Qdrant"""
    info = await qdrant_client.get_collection(COLLECTION_NAME)
    return {
        "total_vectorized": info.points_count,
        "vector_size": info.config.params.vectors.size,
        "distance_metric": str(info.config.params.vectors.distance),
        "model": MODEL_NAME
    }