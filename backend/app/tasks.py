import os
import logging
import requests
from datetime import datetime, timedelta
from celery import Celery
from pymongo import MongoClient

logger = logging.getLogger("medical_veille.tasks")

# ============================================================
# CONFIGURATION
# ============================================================

REDIS_URL    = os.getenv("REDIS_URL",    "redis://redis:6379/0")
RABBITMQ_URL = os.getenv("RABBITMQ_URL", "amqp://meduser:medpassword@rabbitmq:5672//")
MONGO_URL    = os.getenv("MONGO_URL",    "mongodb://meduser:medpassword@mongodb:27017/medical_veille?authSource=admin")

# ============================================================
# CELERY — RabbitMQ broker + Redis backend
# ============================================================

celery = Celery(
    "medical_veille",
    broker=RABBITMQ_URL,
    backend=REDIS_URL,
)

celery.conf.update(
    task_serializer="json",
    result_serializer="json",
    accept_content=["json"],
    task_acks_late=True,
    task_reject_on_worker_lost=True,
    timezone="Europe/Paris",
    enable_utc=True,
)

# ============================================================
# MONGODB SYNCHRONE (Celery est synchrone)
# ============================================================

_sync_client               = MongoClient(MONGO_URL)
_sync_db                   = _sync_client["medical_veille"]
sync_articles_collection   = _sync_db["articles"]
sync_logs_collection       = _sync_db["scraping_logs"]


# ============================================================
# HELPER — Log de scraping
# ============================================================

def _log_scraping(
    keyword: str,
    source: str,
    debut: datetime,
    nb_trouves: int,
    nb_sauvegardes: int,
    nb_doublons: int,
    statut: str,
    erreur: str | None = None
):
    fin = datetime.utcnow()
    sync_logs_collection.insert_one({
        "keyword":               keyword,
        "source":                source,
        "nb_articles_trouves":   nb_trouves,
        "nb_articles_sauvegardes": nb_sauvegardes,
        "nb_doublons":           nb_doublons,
        "statut":                statut,
        "erreur":                erreur,
        "debut":                 debut,
        "fin":                   fin,
        "duree_secondes":        (fin - debut).total_seconds(),
    })


def _publish_kafka(pubmed_id: str, keyword: str, titre: str):
    try:
        from app.database.kafka_producer import publish_article_scraped
        publish_article_scraped(pubmed_id=pubmed_id, keyword=keyword, titre=titre)
    except Exception as e:
        logger.warning(f"Kafka non disponible (ignoré) : {e}")


def _publish_kafka_completed(keyword: str, nb_articles: int):
    try:
        from app.database.kafka_producer import publish_scraping_completed
        publish_scraping_completed(keyword=keyword, nb_articles=nb_articles)
    except Exception as e:
        logger.warning(f"Kafka non disponible (ignoré) : {e}")


# ============================================================
# ✅ VÉRIFICATION DES ALERTES (version synchrone pour Celery)
# ============================================================

def _check_alerts_sync(article: dict):
    """
    Vérifie si un nouvel article déclenche des alertes.
    Version synchrone pour Celery (utilise SQLAlchemy sync).
    """
    try:
        from sqlalchemy import create_engine, select
        from sqlalchemy.orm import sessionmaker
        from app.models import KeywordAlert, AuthorAlert, Notification

        DATABASE_URL = os.getenv("DATABASE_URL", "").replace("+asyncpg", "")
        if not DATABASE_URL:
            return

        engine = create_engine(DATABASE_URL)
        Session = sessionmaker(bind=engine)

        titre     = article.get("titre", "").lower()
        resume    = article.get("resume", "").lower()
        auteurs   = article.get("auteurs", [])
        pubmed_id = article.get("pubmed_id", "")

        with Session() as db:
            # Vérifier alertes mots-clés
            keyword_alerts = db.execute(
                select(KeywordAlert).where(KeywordAlert.is_active == True)
            ).scalars().all()

            for alert in keyword_alerts:
                kw = alert.keyword.lower()
                if kw in titre or kw in resume:
                    notif = Notification(
                        user_id=alert.user_id,
                        type="keyword",
                        titre=f"Nouvel article sur '{alert.keyword}'",
                        message=article.get("titre", ""),
                        pubmed_id=pubmed_id,
                        is_read=False
                    )
                    db.add(notif)
                    logger.info(f"✅ Notification créée — keyword='{alert.keyword}' user={alert.user_id}")

            # Vérifier alertes auteurs
            author_alerts = db.execute(
                select(AuthorAlert).where(AuthorAlert.is_active == True)
            ).scalars().all()

            for alert in author_alerts:
                if isinstance(auteurs, list):
                    matched = any(alert.author_name.lower() in a.lower() for a in auteurs)
                else:
                    matched = alert.author_name.lower() in str(auteurs).lower()

                if matched:
                    notif = Notification(
                        user_id=alert.user_id,
                        type="author",
                        titre=f"Nouvelle publication de {alert.author_name}",
                        message=article.get("titre", ""),
                        pubmed_id=pubmed_id,
                        is_read=False
                    )
                    db.add(notif)
                    logger.info(f"✅ Notification créée — author='{alert.author_name}' user={alert.user_id}")

            db.commit()

    except Exception as e:
        logger.warning(f"Erreur vérification alertes : {e}")


# ============================================================
# SCRAPING PUBMED
# ============================================================

@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_pubmed(self, keyword: str, max_results: int = 20):
    from Bio import Entrez

    debut        = datetime.utcnow()
    nb_trouves   = 0
    nb_sauvegardes = 0
    nb_doublons  = 0

    try:
        Entrez.email = os.getenv("ENTREZ_EMAIL", "veille@medical.com")

        handle = Entrez.esearch(db="pubmed", term=keyword, retmax=max_results, sort="relevance")
        record = Entrez.read(handle)
        handle.close()

        ids = record["IdList"]
        nb_trouves = len(ids)
        logger.info(f"PubMed '{keyword}' → {nb_trouves} articles trouvés")

        if not ids:
            _log_scraping(keyword, "pubmed", debut, 0, 0, 0, "success")
            return {"statut": "success", "message": f"Aucun article pour '{keyword}'"}

        fetch_handle = Entrez.efetch(
            db="pubmed",
            id=",".join(ids),
            rettype="xml",
            retmode="xml"
        )
        records = Entrez.read(fetch_handle)
        fetch_handle.close()

        for article_data in records["PubmedArticle"]:
            try:
                article = _parse_pubmed_article(article_data, keyword)
                result = sync_articles_collection.update_one(
                    {"pubmed_id": article["pubmed_id"]},
                    {"$set": article},
                    upsert=True
                )
                if result.upserted_id:
                    nb_sauvegardes += 1
                    _publish_kafka(article["pubmed_id"], keyword, article.get("titre", ""))
                    # ✅ Vérifier les alertes pour ce nouvel article
                    _check_alerts_sync(article)
                else:
                    nb_doublons += 1

            except Exception as e:
                logger.warning(f"Erreur parsing article PubMed : {e}")
                continue

        if nb_sauvegardes > 0:
            _publish_kafka_completed(keyword, nb_sauvegardes)

        _log_scraping(keyword, "pubmed", debut, nb_trouves, nb_sauvegardes, nb_doublons, "success")
        logger.info(f"PubMed '{keyword}' → {nb_sauvegardes} sauvegardés, {nb_doublons} doublons")

        return {
            "statut":      "success",
            "source":      "pubmed",
            "keyword":     keyword,
            "trouves":     nb_trouves,
            "sauvegardes": nb_sauvegardes,
            "doublons":    nb_doublons,
        }

    except Exception as e:
        _log_scraping(keyword, "pubmed", debut, nb_trouves, nb_sauvegardes, nb_doublons, "error", str(e))
        logger.error(f"Erreur scraping PubMed '{keyword}' : {e}")
        raise self.retry(exc=e)


# ============================================================
# SCRAPING EUROPE PMC
# ============================================================

@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_europe_pmc(self, keyword: str, max_results: int = 20):
    debut        = datetime.utcnow()
    nb_trouves   = 0
    nb_sauvegardes = 0
    nb_doublons  = 0

    try:
        response = requests.get(
            "https://www.ebi.ac.uk/europepmc/webservices/rest/search",
            params={
                "query":      keyword,
                "resultType": "lite",
                "pageSize":   max_results,
                "format":     "json",
            },
            timeout=30
        )
        response.raise_for_status()
        data = response.json()

        result_list = data.get("resultList", {})
        results = result_list.get("result", []) if isinstance(result_list, dict) else []
        nb_trouves = len(results)
        logger.info(f"Europe PMC '{keyword}' → {nb_trouves} articles trouvés")

        if not results:
            _log_scraping(keyword, "europe_pmc", debut, 0, 0, 0, "success")
            return {"statut": "success", "message": f"Aucun article pour '{keyword}'"}

        for item in results:
            try:
                article = _parse_europe_pmc_article(item, keyword)
                result = sync_articles_collection.update_one(
                    {"europe_pmc_id": article["europe_pmc_id"]},
                    {"$set": article},
                    upsert=True
                )
                if result.upserted_id:
                    nb_sauvegardes += 1
                    _publish_kafka(article["europe_pmc_id"], keyword, article.get("titre", ""))
                    # ✅ Vérifier les alertes pour ce nouvel article
                    _check_alerts_sync(article)
                else:
                    nb_doublons += 1

            except Exception as e:
                logger.warning(f"Erreur parsing article Europe PMC : {e}")
                continue

        if nb_sauvegardes > 0:
            _publish_kafka_completed(keyword, nb_sauvegardes)

        _log_scraping(keyword, "europe_pmc", debut, nb_trouves, nb_sauvegardes, nb_doublons, "success")
        logger.info(f"Europe PMC '{keyword}' → {nb_sauvegardes} sauvegardés, {nb_doublons} doublons")

        return {
            "statut":      "success",
            "source":      "europe_pmc",
            "keyword":     keyword,
            "trouves":     nb_trouves,
            "sauvegardes": nb_sauvegardes,
            "doublons":    nb_doublons,
        }

    except Exception as e:
        _log_scraping(keyword, "europe_pmc", debut, nb_trouves, nb_sauvegardes, nb_doublons, "error", str(e))
        logger.error(f"Erreur scraping Europe PMC '{keyword}' : {e}")
        raise self.retry(exc=e)


# ============================================================
# SCRAPING BIORXIV
# ============================================================

@celery.task(bind=True, max_retries=3, default_retry_delay=60)
def scrape_biorxiv(self, keyword: str, max_results: int = 20):
    debut        = datetime.utcnow()
    nb_trouves   = 0
    nb_sauvegardes = 0
    nb_doublons  = 0

    try:
        date_end   = datetime.utcnow().strftime("%Y-%m-%d")
        date_start = (datetime.utcnow() - timedelta(days=30)).strftime("%Y-%m-%d")

        response = requests.get(
            f"https://api.biorxiv.org/details/biorxiv/{date_start}/{date_end}/0/json",
            timeout=60
        )
        response.raise_for_status()
        data = response.json()

        collection = data.get("collection", [])

        kw = keyword.lower()
        filtered = [
            item for item in collection
            if kw in item.get("title",    "").lower()
            or kw in item.get("abstract", "").lower()
            or kw in item.get("category", "").lower()
        ][:max_results]

        nb_trouves = len(filtered)
        logger.info(f"bioRxiv '{keyword}' → {len(collection)} récupérés, {nb_trouves} matchent")

        if not filtered:
            _log_scraping(keyword, "biorxiv", debut, 0, 0, 0, "success")
            return {"statut": "success", "message": f"Aucun article pour '{keyword}'"}

        for item in filtered:
            try:
                article = _parse_biorxiv_article(item, keyword)
                biorxiv_doi = article.get("biorxiv_doi", "")
                if not biorxiv_doi:
                    continue

                result = sync_articles_collection.update_one(
                    {"biorxiv_doi": biorxiv_doi},
                    {"$set": article},
                    upsert=True
                )
                if result.upserted_id:
                    nb_sauvegardes += 1
                    _publish_kafka(biorxiv_doi, keyword, article.get("titre", ""))
                    # ✅ Vérifier les alertes pour ce nouvel article
                    _check_alerts_sync(article)
                else:
                    nb_doublons += 1

            except Exception as e:
                logger.warning(f"Erreur parsing article bioRxiv : {e}")
                continue

        if nb_sauvegardes > 0:
            _publish_kafka_completed(keyword, nb_sauvegardes)

        _log_scraping(keyword, "biorxiv", debut, nb_trouves, nb_sauvegardes, nb_doublons, "success")
        logger.info(f"bioRxiv '{keyword}' → {nb_sauvegardes} sauvegardés, {nb_doublons} doublons")

        return {
            "statut":      "success",
            "source":      "biorxiv",
            "keyword":     keyword,
            "trouves":     nb_trouves,
            "sauvegardes": nb_sauvegardes,
            "doublons":    nb_doublons,
        }

    except Exception as e:
        _log_scraping(keyword, "biorxiv", debut, nb_trouves, nb_sauvegardes, nb_doublons, "error", str(e))
        logger.error(f"Erreur scraping bioRxiv '{keyword}' : {e}")
        raise self.retry(exc=e)


# ============================================================
# PARSERS
# ============================================================

def _parse_pubmed_article(article_data: dict, keyword: str) -> dict:
    try:
        medline = article_data["MedlineCitation"]
        article = medline["Article"]

        titre  = str(article.get("ArticleTitle", "Sans titre"))
        resume = ""
        if "Abstract" in article:
            texts = article["Abstract"].get("AbstractText", [])
            resume = " ".join([str(t) for t in texts]) if isinstance(texts, list) else str(texts)

        auteurs = []
        for author in article.get("AuthorList", []):
            last  = author.get("LastName", "")
            first = author.get("ForeName", "")
            if last:
                auteurs.append(f"{last} {first}".strip())

        date_pub = article.get("Journal", {}).get("JournalIssue", {}).get("PubDate", {})
        annee = str(date_pub.get("Year", date_pub.get("MedlineDate", "")[:4]))
        journal = str(article.get("Journal", {}).get("Title", ""))

        mesh_terms = [str(m["DescriptorName"]) for m in medline.get("MeshHeadingList", [])]
        mots_cles  = [str(kw) for kw_list in medline.get("KeywordList", []) for kw in kw_list]

        pubmed_id = str(medline["PMID"])
        doi = None
        for loc in article.get("ELocationID", []):
            if loc.attributes.get("EIdType") == "doi":
                doi = str(loc)

        return {
            "pubmed_id":         pubmed_id,
            "doi":               doi,
            "titre":             titre,
            "resume":            resume,
            "auteurs":           auteurs,
            "journal":           journal,
            "annee":             annee,
            "mots_cles":         mots_cles,
            "mesh_terms":        mesh_terms,
            "source":            "pubmed",
            "url":               f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/",
            "keyword_recherche": keyword,
            "scraped_at":        datetime.utcnow(),
            "updated_at":        datetime.utcnow(),
            "specialite":        None,
            "sous_specialite":   None,
            "type_etude":        None,
            "est_indexe":        False,
            "est_vectorise":     False,
            "resume_ia":         None,
            "embedding":         None,
            "nb_citations":      0,
        }

    except Exception as e:
        logger.error(f"Erreur parsing PubMed : {e}")
        return {
            "titre":           "Erreur de parsing",
            "source":          "pubmed",
            "specialite":      None,
            "sous_specialite": None,
            "type_etude":      None,
            "est_indexe":      False,
            "est_vectorise":   False,
            "resume_ia":       None,
            "embedding":       None,
            "scraped_at":      datetime.utcnow(),
            "erreur":          str(e),
        }


def _parse_europe_pmc_article(item: dict, keyword: str) -> dict:
    try:
        europe_pmc_id = item.get("id", "")
        titre  = item.get("title", "Sans titre").strip()
        resume = item.get("abstractText", "")

        auteurs = [
            a.get("fullName", "")
            for a in item.get("authorList", {}).get("author", [])
            if a.get("fullName")
        ]

        journal = item.get("journalTitle", "")
        annee   = str(item.get("pubYear", ""))
        doi     = item.get("doi", None)

        mots_cles = [
            kw for kw in item.get("keywordList", {}).get("keyword", [])
            if isinstance(kw, str)
        ]

        return {
            "europe_pmc_id":     europe_pmc_id,
            "pubmed_id":         item.get("pmid", None),
            "doi":               doi,
            "titre":             titre,
            "resume":            resume,
            "auteurs":           auteurs,
            "journal":           journal,
            "annee":             annee,
            "mots_cles":         mots_cles,
            "mesh_terms":        [],
            "source":            "europe_pmc",
            "url":               f"https://europepmc.org/article/MED/{europe_pmc_id}",
            "keyword_recherche": keyword,
            "scraped_at":        datetime.utcnow(),
            "updated_at":        datetime.utcnow(),
            "specialite":        None,
            "sous_specialite":   None,
            "type_etude":        None,
            "est_indexe":        False,
            "est_vectorise":     False,
            "resume_ia":         None,
            "embedding":         None,
            "nb_citations":      item.get("citedByCount", 0),
            "is_open_access":    item.get("isOpenAccess", "N") == "Y",
        }

    except Exception as e:
        logger.error(f"Erreur parsing Europe PMC : {e}")
        return {
            "titre":           "Erreur de parsing",
            "source":          "europe_pmc",
            "specialite":      None,
            "sous_specialite": None,
            "type_etude":      None,
            "est_indexe":      False,
            "est_vectorise":   False,
            "resume_ia":       None,
            "embedding":       None,
            "scraped_at":      datetime.utcnow(),
            "erreur":          str(e),
        }


def _parse_biorxiv_article(item: dict, keyword: str) -> dict:
    try:
        doi      = item.get("doi", "")
        titre    = item.get("title", "Sans titre").strip()
        resume   = item.get("abstract", "")
        auteurs  = [a.strip() for a in item.get("authors", "").split(";") if a.strip()]
        annee    = item.get("date", "")[:4]
        category = item.get("category", "")

        return {
            "biorxiv_doi":       doi,
            "pubmed_id":         f"biorxiv_{doi.replace('/', '_')}" if doi else None,
            "doi":               doi,
            "titre":             titre,
            "resume":            resume,
            "auteurs":           auteurs,
            "journal":           "bioRxiv (preprint)",
            "annee":             annee,
            "mots_cles":         [category] if category else [],
            "mesh_terms":        [],
            "source":            "biorxiv",
            "url":               f"https://www.biorxiv.org/content/{doi}" if doi else "",
            "keyword_recherche": keyword,
            "scraped_at":        datetime.utcnow(),
            "updated_at":        datetime.utcnow(),
            "specialite":        None,
            "sous_specialite":   None,
            "type_etude":        item.get("type", None),
            "est_indexe":        False,
            "est_vectorise":     False,
            "resume_ia":         None,
            "embedding":         None,
            "nb_citations":      0,
            "is_preprint":       True,
        }

    except Exception as e:
        logger.error(f"Erreur parsing bioRxiv : {e}")
        return {
            "titre":           "Erreur de parsing",
            "source":          "biorxiv",
            "specialite":      None,
            "sous_specialite": None,
            "type_etude":      None,
            "est_indexe":      False,
            "est_vectorise":   False,
            "resume_ia":       None,
            "embedding":       None,
            "scraped_at":      datetime.utcnow(),
            "erreur":          str(e),
        }