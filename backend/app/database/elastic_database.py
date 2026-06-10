import os
from typing import Optional
from elasticsearch import AsyncElasticsearch

ELASTIC_URL = os.getenv("ELASTIC_URL", "http://elasticsearch:9200")
INDEX_NAME = "articles"

es_client: Optional[AsyncElasticsearch] = None


async def init_elasticsearch():
    global es_client
    es_client = AsyncElasticsearch([ELASTIC_URL])
    info = await es_client.info()
    print(f"✅ Elasticsearch connecté ! version: {info['version']['number']}")
    await create_articles_index()


async def close_elasticsearch():
    global es_client
    if es_client:
        await es_client.close()


async def create_articles_index():
    exists = await es_client.indices.exists(index=INDEX_NAME)
    if exists:
        print(f"✅ Index '{INDEX_NAME}' déjà existant.")
        return

    mapping = {
        "settings": {
            "number_of_shards": 1,
            "number_of_replicas": 0,
            "analysis": {
                "analyzer": {
                    "medical_analyzer": {
                        "type": "standard",
                        "stopwords": "_english_"
                    }
                }
            }
        },
        "mappings": {
            "properties": {
                "pubmed_id":         {"type": "keyword"},
                "titre":             {"type": "text", "analyzer": "medical_analyzer"},
                "resume":            {"type": "text", "analyzer": "medical_analyzer"},
                "auteurs":           {"type": "keyword"},
                "journal":           {"type": "keyword"},
                "date_publication":  {"type": "date", "format": "yyyy-MM-dd||yyyy||epoch_millis"},
                "mots_cles":         {"type": "keyword"},
                "specialite":        {"type": "keyword"},
                "source":            {"type": "keyword"},  # ✅ AJOUT
                "score_pertinence":  {"type": "float"},
                "est_indexe":        {"type": "boolean"},
                "created_at":        {"type": "date"}
            }
        }
    }

    await es_client.indices.create(index=INDEX_NAME, body=mapping)
    print(f"✅ Index '{INDEX_NAME}' créé avec mapping médical !")


# ============================================================
# INDEXATION
# ============================================================

def _build_doc(article: dict) -> dict:
    """Construit le document à indexer — incluant la source."""
    return {
        "pubmed_id":        article.get("pubmed_id"),
        "titre":            article.get("titre", ""),
        "resume":           article.get("resume") or article.get("resume_ia") or "",
        "auteurs":          article.get("auteurs", []),
        "journal":          article.get("journal", ""),
        "date_publication": article.get("date_publication"),
        "mots_cles":        article.get("mots_cles", []),
        "specialite":       article.get("specialite", ""),
        "source":           article.get("source", "pubmed"),  # ✅ AJOUT
        "score_pertinence": article.get("score_pertinence", 0.0),
        "est_indexe":       True,
    }


async def index_article(article: dict):
    doc = _build_doc(article)
    await es_client.index(
        index=INDEX_NAME,
        id=article.get("pubmed_id"),
        document=doc
    )


async def index_articles_bulk(articles: list[dict]):
    if not articles:
        return 0

    operations = []
    for article in articles:
        operations.append({"index": {"_index": INDEX_NAME, "_id": article.get("pubmed_id")}})
        operations.append(_build_doc(article))

    response = await es_client.bulk(operations=operations)
    indexed = sum(1 for item in response["items"] if item["index"]["status"] in [200, 201])
    print(f"✅ {indexed}/{len(articles)} articles indexés dans Elasticsearch !")
    return indexed


async def delete_article(pubmed_id: str):
    await es_client.delete(index=INDEX_NAME, id=pubmed_id, ignore=[404])


# ============================================================
# RECHERCHE FULL-TEXT
# ============================================================

async def search_articles(
    query: str,
    specialite: Optional[str] = None,
    page: int = 1,
    size: int = 10
) -> dict:
    must = [
        {
            "multi_match": {
                "query": query,
                "fields": ["titre^3", "resume^2", "mots_cles^2", "auteurs", "journal"],
                "type": "best_fields",
                "fuzziness": "AUTO"
            }
        }
    ]

    filters = []
    if specialite:
        filters.append({"term": {"specialite": specialite}})

    es_query = {
        "query": {
            "bool": {
                "must": must,
                "filter": filters
            }
        },
        "highlight": {
            "fields": {
                "titre": {},
                "resume": {"fragment_size": 200, "number_of_fragments": 1}
            }
        },
        "sort": [
            {"_score": {"order": "desc"}},
            {"score_pertinence": {"order": "desc"}}
        ],
        "from": (page - 1) * size,
        "size": size
    }

    response = await es_client.search(index=INDEX_NAME, body=es_query)

    hits = response["hits"]["hits"]
    total = response["hits"]["total"]["value"]

    results = []
    for hit in hits:
        source = hit["_source"]
        source["_score"] = hit["_score"]
        source["_highlight"] = hit.get("highlight", {})
        results.append(source)

    return {
        "total": total,
        "page": page,
        "size": size,
        "pages": (total + size - 1) // size,
        "results": results
    }


async def get_elastic_stats() -> dict:
    stats = await es_client.indices.stats(index=INDEX_NAME)
    count = await es_client.count(index=INDEX_NAME)
    return {
        "total_indexed": count["count"],
        "index_size_mb": round(
            stats["indices"][INDEX_NAME]["total"]["store"]["size_in_bytes"] / (1024 * 1024), 2
        )
    }