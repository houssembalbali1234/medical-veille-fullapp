from fastapi import APIRouter, Query
from typing import Optional
from app.services.network_service import (
    get_researcher_profile,
    get_collaboration_graph,
    get_collaboration_suggestions,
    get_top_researchers
)
from app.services.orcid_service import find_researcher_orcid

router = APIRouter(prefix="/network", tags=["Network"])

# ============================================================
# 👤 PROFIL CHERCHEUR
# ============================================================
@router.get("/researcher/{author_name}", response_model=dict)
async def researcher_profile(author_name: str):
    """
    Profil complet d'un chercheur :
    - Nombre d'articles
    - Spécialités
    - Top co-auteurs
    - Journaux
    """
    return await get_researcher_profile(author_name)

# ============================================================
# 🕸️ GRAPHE DE COLLABORATION
# ============================================================
@router.get("/graph", response_model=dict)
async def collaboration_graph(
    specialite: Optional[str] = Query(None, description="Filtrer par spécialité"),
    limit: int = Query(50, le=200)
):
    """
    Graphe de co-auteurs :
    - nodes : chercheurs
    - edges : collaborations (avec poids)
    Utilisé pour visualiser le réseau de collaboration.
    """
    return await get_collaboration_graph(specialite=specialite, limit=limit)

# ============================================================
# 🤝 SUGGESTIONS DE COLLABORATION
# ============================================================
@router.get("/suggestions/{author_name}", response_model=dict)
async def collaboration_suggestions(
    author_name: str,
    limit: int = Query(5, le=20)
):
    """
    Suggère des collaborateurs potentiels.
    Basé sur l'algorithme amis-d'amis.
    """
    return await get_collaboration_suggestions(author_name=author_name, limit=limit)

# ============================================================
# 🏅 TOP CHERCHEURS
# ============================================================
@router.get("/top-researchers", response_model=list)
async def top_researchers(
    specialite: Optional[str] = Query(None),
    limit: int = Query(10, le=50)
):
    """
    Chercheurs les plus prolifiques.
    Classés par nombre d'articles publiés.
    """
    return await get_top_researchers(specialite=specialite, limit=limit)

# ============================================================
# 🎓 ORCID — Profil officiel chercheur
# ============================================================
@router.get("/orcid/{author_name}", response_model=dict)
async def get_orcid_profile(author_name: str):
    """
    Recherche le profil ORCID officiel d'un chercheur.
    Retourne : orcid_id, orcid_url, nom, keywords, publications ORCID.
    """
    profile = await find_researcher_orcid(author_name)

    if not profile:
        return {
            "found": False,
            "author_name": author_name,
            "message": "Aucun profil ORCID trouvé pour ce chercheur"
        }

    return {
        "found": True,
        "author_name": author_name,
        **profile
    }