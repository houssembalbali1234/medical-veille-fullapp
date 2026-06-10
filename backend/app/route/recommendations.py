from fastapi import APIRouter, Depends, HTTPException, Query
from typing import Optional
from app.database.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import get_current_user
from app.services.recommendation import (
    record_interaction,
    get_recommendations,
    save_article,
    get_saved_articles,
    get_user_stats
)

router = APIRouter(prefix="/recommendations", tags=["Recommendations"])


# ============================================================
# 📊 INTERACTIONS
# ============================================================

@router.post("/interaction", response_model=dict)
async def add_interaction(
    pubmed_id: str,
    interaction_type: str = Query(..., description="view, like, save, share, dislike"),
    specialite: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Enregistre une interaction utilisateur avec un article.
    
    Types disponibles :
    - view    → l'utilisateur a consulté l'article (+1.0)
    - like    → l'utilisateur aime l'article (+3.0)
    - save    → l'utilisateur sauvegarde (+2.0)
    - share   → l'utilisateur partage (+2.5)
    - dislike → l'utilisateur n'aime pas (-2.0)
    """
    result = await record_interaction(
        user_id=str(current_user.id),
        pubmed_id=pubmed_id,
        interaction_type=interaction_type,
        specialite=specialite,
        db=db
    )
    return result


# ============================================================
# 🎯 FEED PERSONNALISÉ
# ============================================================

@router.get("/feed", response_model=dict)
async def get_personalized_feed(
    limit: int = Query(10, le=50),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Retourne un feed personnalisé pour l'utilisateur connecté.
    
    Algorithme hybride :
    - Si l'utilisateur a des interactions → recommandations basées sur ses préférences
    - Si nouvel utilisateur → articles récents populaires
    """
    recommendations = await get_recommendations(
        user_id=str(current_user.id),
        limit=limit,
        db=db
    )

    return {
        "user_id": str(current_user.id),
        "total": len(recommendations),
        "recommendations": recommendations
    }


# ============================================================
# 📚 BIBLIOTHÈQUE PERSONNELLE
# ============================================================

@router.post("/save", response_model=dict)
async def save_article_endpoint(
    pubmed_id: str,
    titre: str = Query(""),
    specialite: Optional[str] = Query(None),
    note: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Sauvegarde un article dans la bibliothèque personnelle"""
    result = await save_article(
        user_id=str(current_user.id),
        pubmed_id=pubmed_id,
        titre=titre,
        specialite=specialite,
        note=note,
        db=db
    )
    return result


@router.get("/saved", response_model=dict)
async def get_saved(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Récupère les articles sauvegardés par l'utilisateur"""
    saved = await get_saved_articles(
        user_id=str(current_user.id),
        db=db
    )
    return {
        "total": len(saved),
        "articles": saved
    }


# ============================================================
# 📈 STATISTIQUES UTILISATEUR
# ============================================================

@router.get("/stats", response_model=dict)
async def get_stats(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Statistiques personnelles :
    - Nombre d'interactions
    - Spécialités préférées
    - Articles sauvegardés
    """
    stats = await get_user_stats(
        user_id=str(current_user.id),
        db=db
    )
    return stats