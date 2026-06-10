"""
orcid_service.py — Intégration ORCID
=====================================
Recherche et récupère les profils officiels des chercheurs via l'API publique ORCID.
API publique — pas d'authentification requise.
"""

import httpx
import xml.etree.ElementTree as ET
import logging

logger = logging.getLogger("medical_veille.orcid")

ORCID_BASE = "https://pub.orcid.org/v3.0"
HEADERS = {"Accept": "application/vnd.orcid+xml"}

# Namespaces XML ORCID
NS = {
    "person": "http://www.orcid.org/ns/person",
    "personal-details": "http://www.orcid.org/ns/personal-details",
    "common": "http://www.orcid.org/ns/common",
    "search": "http://www.orcid.org/ns/search",
    "employment": "http://www.orcid.org/ns/employment",
    "keyword": "http://www.orcid.org/ns/keyword",
    "researcher-url": "http://www.orcid.org/ns/researcher-url",
    "activities": "http://www.orcid.org/ns/activities",
    "work": "http://www.orcid.org/ns/work",
}


async def search_orcid(nom: str, max_results: int = 3) -> list[dict]:
    """
    Recherche un chercheur par nom dans ORCID.
    Retourne une liste d'identifiants ORCID trouvés.
    """
    parts = nom.strip().split()
    if len(parts) >= 2:
        family = parts[-1]
        query = f"family-name:{family}"
    else:
        query = f"family-name:{nom}"

    url = f"{ORCID_BASE}/search"
    params = {"q": query, "rows": max_results}

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url, params=params, headers=HEADERS)
            res.raise_for_status()

        root = ET.fromstring(res.text)
        results = []
        for result in root.findall(".//search:result", NS):
            orcid_el = result.find("common:orcid-identifier/common:path", NS)
            if orcid_el is not None:
                results.append(orcid_el.text)

        return results

    except Exception as e:
        logger.error(f"Erreur ORCID search '{nom}': {e}")
        return []


async def get_orcid_profile(orcid_id: str) -> dict | None:
    """
    Récupère le profil complet d'un chercheur via son ORCID ID.
    Retourne nom, institution, mots-clés, URL.
    """
    url = f"{ORCID_BASE}/{orcid_id}/person"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url, headers=HEADERS)
            res.raise_for_status()

        root = ET.fromstring(res.text)

        # Nom
        given = root.find(".//personal-details:given-names", NS)
        family = root.find(".//personal-details:family-name", NS)
        nom = ""
        if given is not None and family is not None:
            nom = f"{given.text} {family.text}"
        elif family is not None:
            nom = family.text or ""

        # Mots-clés
        keywords = []
        for kw in root.findall(".//keyword:keyword/keyword:content", NS):
            if kw.text:
                keywords.append(kw.text)

        # URL personnelle
        urls = []
        for url_el in root.findall(".//researcher-url:url", NS):
            if url_el.text:
                urls.append(url_el.text)

        return {
            "orcid_id": orcid_id,
            "orcid_url": f"https://orcid.org/{orcid_id}",
            "nom": nom,
            "keywords": keywords[:5],
            "urls": urls[:2],
        }

    except Exception as e:
        logger.error(f"Erreur ORCID profile '{orcid_id}': {e}")
        return None


async def get_orcid_works(orcid_id: str, max_works: int = 5) -> list[dict]:
    """
    Récupère les publications d'un chercheur via son ORCID ID.
    """
    url = f"{ORCID_BASE}/{orcid_id}/works"

    try:
        async with httpx.AsyncClient(timeout=10) as client:
            res = await client.get(url, headers=HEADERS)
            res.raise_for_status()

        root = ET.fromstring(res.text)
        works = []

        for work in root.findall(".//work:work-summary", NS):
            title_el = work.find(".//common:title", NS)
            year_el = work.find(".//common:publication-date/common:year", NS)
            doi_el = work.find(".//common:external-id[common:external-id-type='doi']/common:external-id-value", NS)

            if title_el is not None:
                works.append({
                    "titre": title_el.text or "",
                    "annee": year_el.text if year_el is not None else "",
                    "doi": doi_el.text if doi_el is not None else "",
                })

            if len(works) >= max_works:
                break

        return works

    except Exception as e:
        logger.error(f"Erreur ORCID works '{orcid_id}': {e}")
        return []


async def find_researcher_orcid(nom: str) -> dict | None:
    """
    Fonction principale : cherche un chercheur par nom et retourne son profil ORCID complet.
    Utilisée dans la page réseau pour enrichir les profils.
    """
    orcid_ids = await search_orcid(nom, max_results=3)

    if not orcid_ids:
        return None

    # Prendre le premier résultat
    profile = await get_orcid_profile(orcid_ids[0])
    if profile:
        works = await get_orcid_works(orcid_ids[0], max_works=3)
        profile["publications_orcid"] = works

    return profile