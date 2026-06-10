# app/services/pubmed_service.py
"""
Service PubMed — Scraping via API Entrez (sans BioPython)
==========================================================
Alternative légère à tasks.py pour des recherches ponctuelles.
Utilise l'API REST d'NCBI directement (pas de BioPython).

Différence avec tasks.py :
- tasks.py  → scraping en masse via Celery (asynchrone, lourd)
- Ce fichier → recherche ponctuelle synchrone (léger, rapide)
"""

import requests
import xml.etree.ElementTree as ET
import logging
import os
from typing import Optional

logger = logging.getLogger("medical_veille.pubmed")

BASE_URL = "https://eutils.ncbi.nlm.nih.gov/entrez/eutils/"
ENTREZ_EMAIL = os.getenv("ENTREZ_EMAIL", "veille@medical.com")
TIMEOUT = 30  # secondes


# ============================================================
# 🔍 RECHERCHE — Récupère les IDs des articles
# ============================================================

def search_articles(query: str, max_results: int = 10) -> list[str]:
    """
    Cherche des articles PubMed et retourne leurs IDs.

    Args:
        query       : terme de recherche (ex: "diabetes treatment 2024")
        max_results : nombre max d'IDs à retourner

    Returns:
        Liste de PubMed IDs (strings)
        Retourne [] si erreur ou aucun résultat
    """
    try:
        response = requests.get(
            BASE_URL + "esearch.fcgi",
            params={
                "db":      "pubmed",
                "term":    query,
                "retmax":  max_results,
                "retmode": "json",
                "email":   ENTREZ_EMAIL,
                "sort":    "relevance",
            },
            timeout=TIMEOUT
        )
        response.raise_for_status()
        data = response.json()

        ids = data.get("esearchresult", {}).get("idlist", [])
        logger.info(f"PubMed search '{query}' → {len(ids)} IDs trouvés")
        return ids

    except requests.Timeout:
        logger.error(f"Timeout lors de la recherche PubMed '{query}'")
        return []
    except requests.RequestException as e:
        logger.error(f"Erreur réseau PubMed search : {e}")
        return []
    except (KeyError, ValueError) as e:
        logger.error(f"Erreur parsing réponse PubMed : {e}")
        return []


# ============================================================
# 📄 DÉTAILS — Récupère et parse les articles complets
# ============================================================

def fetch_article_details(ids: list[str]) -> list[dict]:
    """
    Récupère les détails complets des articles par leurs IDs.

    Args:
        ids : liste de PubMed IDs

    Returns:
        Liste de dicts avec les champs :
        pubmed_id, titre, auteurs, resume, journal, annee, doi, url
    """
    if not ids:
        return []

    try:
        response = requests.get(
            BASE_URL + "efetch.fcgi",
            params={
                "db":      "pubmed",
                "id":      ",".join(ids),
                "retmode": "xml",
                "rettype": "abstract",
                "email":   ENTREZ_EMAIL,
            },
            timeout=TIMEOUT
        )
        response.raise_for_status()

        return _parse_xml(response.text)

    except requests.Timeout:
        logger.error("Timeout lors du fetch PubMed")
        return []
    except requests.RequestException as e:
        logger.error(f"Erreur réseau PubMed fetch : {e}")
        return []


# ============================================================
# 🛠️ PARSING XML
# ============================================================

def _parse_xml(xml_text: str) -> list[dict]:
    """
    Parse le XML PubMed et extrait les champs utiles.
    """
    articles = []

    try:
        root = ET.fromstring(xml_text)
    except ET.ParseError as e:
        logger.error(f"Erreur parsing XML PubMed : {e}")
        return []

    for article_xml in root.findall(".//PubmedArticle"):
        try:
            medline = article_xml.find("MedlineCitation")
            article = medline.find("Article")

            # ── Titre ─────────────────────────────────────
            titre_el = article.find("ArticleTitle")
            titre = titre_el.text or "Sans titre" if titre_el is not None else "Sans titre"

            # ── Résumé ────────────────────────────────────
            resume = ""
            abstract = article.find("Abstract")
            if abstract is not None:
                texts = abstract.findall("AbstractText")
                resume = " ".join([
                    (t.text or "") for t in texts if t.text
                ])

            # ── Auteurs ───────────────────────────────────
            auteurs = []
            author_list = article.find("AuthorList")
            if author_list is not None:
                for author in author_list.findall("Author"):
                    last  = author.findtext("LastName", "")
                    first = author.findtext("ForeName", "")
                    if last:
                        auteurs.append(f"{last} {first}".strip())

            # ── Journal ───────────────────────────────────
            journal = article.findtext(".//Journal/Title", "")

            # ── Année ─────────────────────────────────────
            annee = (
                article.findtext(".//Journal/JournalIssue/PubDate/Year", "") or
                article.findtext(".//Journal/JournalIssue/PubDate/MedlineDate", "")[:4]
            )

            # ── PubMed ID ─────────────────────────────────
            pmid_el = medline.find("PMID")
            pubmed_id = pmid_el.text if pmid_el is not None else ""

            # ── DOI ───────────────────────────────────────
            doi = ""
            for loc in article.findall("ELocationID"):
                if loc.get("EIdType") == "doi":
                    doi = loc.text or ""
                    break

            articles.append({
                "pubmed_id": pubmed_id,
                "titre":     titre,
                "auteurs":   auteurs,
                "resume":    resume,
                "journal":   journal,
                "annee":     annee,
                "doi":       doi,
                "url":       f"https://pubmed.ncbi.nlm.nih.gov/{pubmed_id}/",
                "source":    "pubmed",
            })

        except Exception as e:
            logger.warning(f"Erreur parsing article PubMed : {e}")
            continue

    logger.info(f"PubMed fetch → {len(articles)} articles parsés")
    return articles


# ============================================================
# 🚀 FONCTION PRINCIPALE — search + fetch en une fois
# ============================================================

def search_and_fetch(
    query: str,
    max_results: int = 10
) -> list[dict]:
    """
    Raccourci : cherche les IDs puis récupère les détails.

    Usage :
        articles = search_and_fetch("diabetes treatment", max_results=5)
        for a in articles:
            print(a["titre"], a["auteurs"])
    """
    ids = search_articles(query, max_results)
    if not ids:
        return []
    return fetch_article_details(ids)