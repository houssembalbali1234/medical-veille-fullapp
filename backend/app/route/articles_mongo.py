from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional, List
from bson import ObjectId
from app.database.mongo_database import get_mongo_db
from app.shemas.mongo_schemas import ArticleMongoResponse, ArticleSearchRequest
from app.database.redis_database import cache_get, cache_set
from app.database.elastic_database import (
    search_articles as es_search,
    index_article,
    index_articles_bulk,
    get_elastic_stats
)
from app.database.qdrant_database import (
    search_similar,
    vectorize_article,
    vectorize_articles_bulk,
    get_qdrant_stats
)
from app.services.classifier import classify_article, classify_all_articles
from app.services.llama_service import generate_resume_for_article, generate_resumes_bulk

router = APIRouter(prefix="/articles", tags=["Articles"])


def serialize_article(article: dict) -> dict:
    if "_id" in article:
        article["id"] = str(article["_id"])
        del article["_id"]
    article.pop("embedding", None)
    return article


@router.get("/logs/scraping", response_model=List[dict])
async def get_scraping_logs(limite: int = Query(20, le=100), db=Depends(get_mongo_db)):
    cursor = db["scraping_logs"].find({}).sort("debut", -1).limit(limite)
    logs = await cursor.to_list(length=limite)
    return [serialize_article(l) for l in logs]


@router.get("/stats", response_model=dict)
async def get_stats(db=Depends(get_mongo_db)):
    cached = await cache_get("articles:stats")
    if cached:
        return cached
    total = await db["articles"].count_documents({})
    pipeline_source = [{"$group": {"_id": "$source", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}]
    sources = await db["articles"].aggregate(pipeline_source).to_list(length=20)
    pipeline_specialite = [{"$match": {"specialite": {"$ne": None}}}, {"$group": {"_id": "$specialite", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}, {"$limit": 10}]
    specialites = await db["articles"].aggregate(pipeline_specialite).to_list(length=10)
    pipeline_annee = [{"$match": {"annee": {"$ne": "", "$ne": None}}}, {"$group": {"_id": "$annee", "count": {"$sum": 1}}}, {"$sort": {"_id": -1}}, {"$limit": 10}]
    annees = await db["articles"].aggregate(pipeline_annee).to_list(length=10)
    pipeline_type_etude = [{"$match": {"type_etude": {"$ne": None}}}, {"$group": {"_id": "$type_etude", "count": {"$sum": 1}}}, {"$sort": {"count": -1}}, {"$limit": 10}]
    types_etude = await db["articles"].aggregate(pipeline_type_etude).to_list(length=10)
    result = {
        "total_articles": total,
        "par_source": {s["_id"]: s["count"] for s in sources},
        "par_specialite": {s["_id"]: s["count"] for s in specialites},
        "par_annee": {a["_id"]: a["count"] for a in annees},
        "par_type_etude": {t["_id"]: t["count"] for t in types_etude}
    }
    await cache_set("articles:stats", result, ttl_seconds=300)
    return result


@router.get("/search/elastic", response_model=dict)
async def search_elastic(q: str = Query(...), specialite: Optional[str] = Query(None), page: int = Query(1, ge=1), size: int = Query(10, le=100)):
    return await es_search(query=q, specialite=specialite, page=page, size=size)


@router.get("/search/elastic/stats", response_model=dict)
async def elastic_stats():
    return await get_elastic_stats()


@router.get("/search/semantic", response_model=dict)
async def search_semantic(q: str = Query(...), specialite: Optional[str] = Query(None), limit: int = Query(10, le=50), score_threshold: float = Query(0.3, ge=0.0, le=1.0)):
    results = await search_similar(query=q, specialite=specialite, limit=limit, score_threshold=score_threshold)
    return {"query": q, "total": len(results), "score_threshold": score_threshold, "results": results}


@router.get("/search/semantic/stats", response_model=dict)
async def qdrant_stats():
    return await get_qdrant_stats()


@router.post("/index-all", response_model=dict)
async def index_all_articles(db=Depends(get_mongo_db)):
    cursor = db["articles"].find({"est_indexe": {"$ne": True}}, {"embedding": 0})
    articles = await cursor.to_list(length=10000)
    if not articles:
        return {"message": "Tous les articles sont déjà indexés ✅", "indexed": 0}
    serialized = [serialize_article(a) for a in articles]
    indexed = await index_articles_bulk(serialized)
    pubmed_ids = [a.get("pubmed_id") for a in serialized if a.get("pubmed_id")]
    if pubmed_ids:
        await db["articles"].update_many({"pubmed_id": {"$in": pubmed_ids}}, {"$set": {"est_indexe": True}})
    return {"message": f"✅ {indexed} articles indexés dans Elasticsearch !", "indexed": indexed, "total_found": len(articles)}


@router.post("/index/{pubmed_id}", response_model=dict)
async def index_one_article(pubmed_id: str, db=Depends(get_mongo_db)):
    article = await db["articles"].find_one({"pubmed_id": pubmed_id}, {"embedding": 0})
    if not article:
        raise HTTPException(status_code=404, detail="Article non trouvé")
    serialized = serialize_article(article)
    await index_article(serialized)
    await db["articles"].update_one({"pubmed_id": pubmed_id}, {"$set": {"est_indexe": True}})
    return {"message": f"✅ Article {pubmed_id} indexé dans Elasticsearch !"}


@router.post("/vectorize-all", response_model=dict)
async def vectorize_all_articles(db=Depends(get_mongo_db)):
    cursor = db["articles"].find({"est_vectorise": {"$ne": True}}, {"embedding": 0})
    articles = await cursor.to_list(length=10000)
    if not articles:
        return {"message": "Tous les articles sont déjà vectorisés ✅", "vectorized": 0}
    serialized = [serialize_article(a) for a in articles]
    vectorized = await vectorize_articles_bulk(serialized)
    pubmed_ids = [a.get("pubmed_id") for a in serialized if a.get("pubmed_id")]
    if pubmed_ids:
        await db["articles"].update_many({"pubmed_id": {"$in": pubmed_ids}}, {"$set": {"est_vectorise": True}})
    return {"message": f"✅ {vectorized} articles vectorisés dans Qdrant !", "vectorized": vectorized, "total_found": len(articles)}


@router.post("/vectorize/{pubmed_id}", response_model=dict)
async def vectorize_one_article(pubmed_id: str, db=Depends(get_mongo_db)):
    article = await db["articles"].find_one({"pubmed_id": pubmed_id}, {"embedding": 0})
    if not article:
        raise HTTPException(status_code=404, detail="Article non trouvé")
    serialized = serialize_article(article)
    success = await vectorize_article(serialized)
    if not success:
        raise HTTPException(status_code=400, detail="Impossible de vectoriser cet article")
    await db["articles"].update_one({"pubmed_id": pubmed_id}, {"$set": {"est_vectorise": True}})
    return {"message": f"✅ Article {pubmed_id} vectorisé dans Qdrant !"}


@router.get("/", response_model=List[dict])
async def get_articles(
    specialite: Optional[str] = Query(None),
    source: Optional[str] = Query(None),
    annee: Optional[str] = Query(None),
    type_etude: Optional[str] = Query(None),
    est_vectorise: Optional[bool] = Query(None),
    est_indexe: Optional[bool] = Query(None),
    limite: int = Query(20, le=100),
    page: int = Query(1, ge=1),
    db=Depends(get_mongo_db)
):
    filtre = {}
    if specialite: filtre["specialite"] = specialite
    if source: filtre["source"] = source
    if annee: filtre["annee"] = annee
    if type_etude: filtre["type_etude"] = type_etude
    if est_vectorise is not None: filtre["est_vectorise"] = est_vectorise
    if est_indexe is not None: filtre["est_indexe"] = est_indexe
    skip = (page - 1) * limite
    cursor = db["articles"].find(filtre, {"embedding": 0}).skip(skip).limit(limite).sort("scraped_at", -1)
    articles = await cursor.to_list(length=limite)
    return [serialize_article(a) for a in articles]


@router.post("/resume-ia/all", response_model=dict)
async def generate_all_resumes(limit: int = Query(10, le=50), db=Depends(get_mongo_db)):
    return await generate_resumes_bulk(limit=limit)


@router.post("/resume-ia/{pubmed_id}", response_model=dict)
async def generate_one_resume(pubmed_id: str, db=Depends(get_mongo_db)):
    return await generate_resume_for_article(pubmed_id, db)


@router.post("/classify-all", response_model=dict)
async def classify_all(db=Depends(get_mongo_db)):
    result = await classify_all_articles()
    from app.database.redis_database import cache_set
    await cache_set("articles:stats", None, ttl_seconds=1)
    return result


@router.post("/classify/{pubmed_id}", response_model=dict)
async def classify_one(pubmed_id: str, db=Depends(get_mongo_db)):
    article = await db["articles"].find_one({"pubmed_id": pubmed_id}, {"embedding": 0})
    if not article:
        raise HTTPException(status_code=404, detail="Article non trouvé")
    serialized = serialize_article(article)
    result = classify_article(serialized)
    await db["articles"].update_one(
        {"pubmed_id": pubmed_id},
        {"$set": {"specialite": result["specialite"], "type_etude": result["type_etude"]}}
    )
    return {"pubmed_id": pubmed_id, "specialite": result["specialite"], "type_etude": result["type_etude"], "message": "✅ Article classifié !"}


# ✅ GET par _id MongoDB
@router.get("/id/{article_id}", response_model=dict)
async def get_article_by_object_id(article_id: str, db=Depends(get_mongo_db)):
    """Récupérer un article par son _id MongoDB"""
    try:
        article = await db["articles"].find_one({"_id": ObjectId(article_id)}, {"embedding": 0})
    except Exception:
        raise HTTPException(status_code=400, detail="ID invalide")
    if not article:
        raise HTTPException(status_code=404, detail="Article non trouvé")
    return serialize_article(article)


# ✅ TRANSLATE par _id MongoDB
@router.post("/{article_id}/translate")
async def translate_mongo_article(article_id: str, db=Depends(get_mongo_db)):
    """Traduit le titre et résumé d'un article MongoDB en français via Llama 3.1"""
    from app.services.llama_service import translate_to_french
    try:
        article = await db["articles"].find_one({"_id": ObjectId(article_id)}, {"embedding": 0})
    except Exception:
        raise HTTPException(status_code=400, detail="ID invalide")
    if not article:
        raise HTTPException(status_code=404, detail="Article non trouvé")
    titre_fr = translate_to_french(article.get("titre", ""))
    resume_fr = translate_to_french(article.get("resume", "")) if article.get("resume") else ""
    return {"article_id": article_id, "titre_fr": titre_fr, "resume_fr": resume_fr}


# ✅ GET par pubmed_id — DOIT ÊTRE EN DERNIER
@router.get("/{pubmed_id}", response_model=dict)
async def get_article(pubmed_id: str, db=Depends(get_mongo_db)):
    cached = await cache_get(f"article:{pubmed_id}")
    if cached:
        return cached
    article = await db["articles"].find_one({"pubmed_id": pubmed_id}, {"embedding": 0})
    if not article:
        raise HTTPException(status_code=404, detail="Article non trouvé")
    result = serialize_article(article)
    await cache_set(f"article:{pubmed_id}", result, ttl_seconds=600)
    return result