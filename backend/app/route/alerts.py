from fastapi import APIRouter, Depends, Query
from typing import Optional
from app.database.database import get_db
from sqlalchemy.ext.asyncio import AsyncSession
from app.auth import get_current_user
from app.services.alert_service import (
    create_keyword_alert,
    create_author_alert,
    get_user_alerts,
    delete_keyword_alert,
    delete_author_alert,
    get_notifications,
    mark_as_read,
    generate_weekly_digest
)

router = APIRouter(prefix="/alerts", tags=["Alerts"])


# ============================================================
# 🔔 ALERTES MOT-CLÉ
# ============================================================

@router.post("/keyword", response_model=dict)
async def add_keyword_alert(
    keyword: str,
    specialite: Optional[str] = Query(None),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Crée une alerte sur un mot-clé.
    Notification dès qu'un article contient ce mot-clé.
    """
    return await create_keyword_alert(
        user_id=str(current_user.id),
        keyword=keyword,
        specialite=specialite,
        db=db
    )


@router.delete("/keyword/{keyword}", response_model=dict)
async def remove_keyword_alert(
    keyword: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Supprime une alerte mot-clé."""
    return await delete_keyword_alert(
        user_id=str(current_user.id),
        keyword=keyword,
        db=db
    )


# ============================================================
# 👤 SUIVI AUTEURS (KOL)
# ============================================================

@router.post("/author", response_model=dict)
async def add_author_alert(
    author_name: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Suit un auteur (Key Opinion Leader).
    Notification dès qu'il publie un nouvel article.
    """
    return await create_author_alert(
        user_id=str(current_user.id),
        author_name=author_name,
        db=db
    )


@router.delete("/author/{author_name}", response_model=dict)
async def remove_author_alert(
    author_name: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Supprime le suivi d'un auteur."""
    return await delete_author_alert(
        user_id=str(current_user.id),
        author_name=author_name,
        db=db
    )


# ============================================================
# 📋 MES ALERTES
# ============================================================

@router.get("/", response_model=dict)
async def get_alerts(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Récupère toutes les alertes actives de l'utilisateur."""
    return await get_user_alerts(
        user_id=str(current_user.id),
        db=db
    )


# ============================================================
# 🔔 NOTIFICATIONS
# ============================================================

@router.get("/notifications", response_model=dict)
async def get_my_notifications(
    unread_only: bool = Query(False),
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Récupère les notifications de l'utilisateur.
    unread_only=true → uniquement les non lues
    """
    return await get_notifications(
        user_id=str(current_user.id),
        unread_only=unread_only,
        db=db
    )


@router.put("/notifications/{notification_id}/read", response_model=dict)
async def read_notification(
    notification_id: str,
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """Marque une notification comme lue."""
    return await mark_as_read(
        user_id=str(current_user.id),
        notification_id=notification_id,
        db=db
    )


# ============================================================
# 📊 DIGEST HEBDOMADAIRE
# ============================================================

@router.get("/digest", response_model=dict)
async def weekly_digest(
    current_user=Depends(get_current_user),
    db: AsyncSession = Depends(get_db)
):
    """
    Génère le digest hebdomadaire personnalisé.
    Résume les nouveaux articles de la semaine
    basé sur les préférences de l'utilisateur.
    """
    return await generate_weekly_digest(
        user_id=str(current_user.id),
        db=db
    )