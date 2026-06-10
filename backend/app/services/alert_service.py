import uuid
import logging
from datetime import datetime, timedelta
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import KeywordAlert, AuthorAlert, Notification, UserPreference

logger = logging.getLogger("medical_veille.alerts")


# ============================================================
# 🔔 ALERTES MOT-CLÉ
# ============================================================

async def create_keyword_alert(
    user_id: str,
    keyword: str,
    specialite: str | None,
    db: AsyncSession
) -> dict:
    """
    Crée une alerte sur un mot-clé.
    Ex: "immunotherapy" → notification dès qu'un article sort.
    Vérifie si l'alerte existe déjà avant de créer.
    """
    existing = await db.execute(
        select(KeywordAlert).where(
            KeywordAlert.user_id == uuid.UUID(user_id),
            KeywordAlert.keyword  == keyword.lower()
        )
    )
    if existing.scalar_one_or_none():
        return {"message": "Alerte déjà existante", "keyword": keyword}

    db.add(KeywordAlert(
        user_id=uuid.UUID(user_id),
        keyword=keyword.lower(),
        specialite=specialite,
        is_active=True
    ))
    await db.commit()

    logger.info(f"Alerte keyword créée — user={user_id} keyword='{keyword}'")
    return {
        "message":   f"Alerte créée pour '{keyword}' !",
        "keyword":   keyword,
        "specialite": specialite,
    }


async def create_author_alert(
    user_id: str,
    author_name: str,
    db: AsyncSession
) -> dict:
    """
    Crée une alerte sur un auteur (KOL — Key Opinion Leader).
    Ex: suivre Dr. Levey → notification dès qu'il publie.
    """
    existing = await db.execute(
        select(AuthorAlert).where(
            AuthorAlert.user_id     == uuid.UUID(user_id),
            AuthorAlert.author_name == author_name
        )
    )
    if existing.scalar_one_or_none():
        return {"message": "Alerte déjà existante", "author": author_name}

    db.add(AuthorAlert(
        user_id=uuid.UUID(user_id),
        author_name=author_name,
        is_active=True
    ))
    await db.commit()

    logger.info(f"Alerte auteur créée — user={user_id} author='{author_name}'")
    return {
        "message":     f"Suivi activé pour '{author_name}' !",
        "author_name": author_name,
    }


async def get_user_alerts(user_id: str, db: AsyncSession) -> dict:
    """Récupère toutes les alertes actives d'un utilisateur."""
    uid = uuid.UUID(user_id)

    kw_result = await db.execute(
        select(KeywordAlert).where(
            KeywordAlert.user_id  == uid,
            KeywordAlert.is_active == True
        )
    )
    auth_result = await db.execute(
        select(AuthorAlert).where(
            AuthorAlert.user_id  == uid,
            AuthorAlert.is_active == True
        )
    )

    keyword_alerts = kw_result.scalars().all()
    author_alerts  = auth_result.scalars().all()

    return {
        "keyword_alerts": [
            {"keyword": a.keyword, "specialite": a.specialite}
            for a in keyword_alerts
        ],
        "author_alerts": [
            {"author_name": a.author_name}
            for a in author_alerts
        ],
        "total": len(keyword_alerts) + len(author_alerts),
    }


async def delete_keyword_alert(user_id: str, keyword: str, db: AsyncSession) -> dict:
    """Supprime une alerte mot-clé."""
    result = await db.execute(
        select(KeywordAlert).where(
            KeywordAlert.user_id == uuid.UUID(user_id),
            KeywordAlert.keyword == keyword.lower()
        )
    )
    alert = result.scalar_one_or_none()
    if not alert:
        return {"message": "Alerte non trouvée"}

    await db.delete(alert)
    await db.commit()
    logger.info(f"Alerte keyword supprimée — user={user_id} keyword='{keyword}'")
    return {"message": f"Alerte '{keyword}' supprimée !"}


async def delete_author_alert(user_id: str, author_name: str, db: AsyncSession) -> dict:
    """Supprime une alerte auteur."""
    result = await db.execute(
        select(AuthorAlert).where(
            AuthorAlert.user_id     == uuid.UUID(user_id),
            AuthorAlert.author_name == author_name
        )
    )
    alert = result.scalar_one_or_none()
    if not alert:
        return {"message": "Alerte non trouvée"}

    await db.delete(alert)
    await db.commit()
    logger.info(f"Alerte auteur supprimée — user={user_id} author='{author_name}'")
    return {"message": f"Suivi '{author_name}' supprimé !"}


# ============================================================
# 🔔 VÉRIFICATION DES ALERTES (appelée après scraping)
# ============================================================

async def check_alerts_for_article(article: dict, db: AsyncSession):
    """
    Vérifie si un nouvel article déclenche des alertes.
    Appelée après chaque scraping pour chaque nouvel article.

    Vérifie :
    1. Si le titre/résumé contient un mot-clé suivi
    2. Si un des auteurs est suivi (KOL)

    Pour chaque match :
    - Crée une Notification en PostgreSQL
    - Push WebSocket temps réel si l'utilisateur est connecté
    - (optionnel) Email d'alerte immédiate
    """
    titre     = article.get("titre", "").lower()
    resume    = article.get("resume", "").lower()
    auteurs   = article.get("auteurs", [])
    pubmed_id = article.get("pubmed_id", "")

    from app.websockets.manager import ws_manager

    # ── 1. Alertes mots-clés ──────────────────────────────
    kw_result = await db.execute(
        select(KeywordAlert).where(KeywordAlert.is_active == True)
    )
    for alert in kw_result.scalars().all():
        kw = alert.keyword.lower()
        if kw not in titre and kw not in resume:
            continue

        # Créer notification PostgreSQL
        notif = Notification(
            user_id=alert.user_id,
            type="keyword",
            titre=f"Nouvel article sur '{alert.keyword}'",
            message=article.get("titre", ""),
            pubmed_id=pubmed_id,
            is_read=False
        )
        db.add(notif)

        # Push WebSocket temps réel
        await _push_ws(
            user_id=str(alert.user_id),
            notification_type="keyword",
            titre=f"Nouvel article sur '{alert.keyword}'",
            message=article.get("titre", ""),
            pubmed_id=pubmed_id,
            ws_manager=ws_manager
        )

        logger.info(f"Alerte keyword déclenchée — keyword='{alert.keyword}' user={alert.user_id}")

    # ── 2. Alertes auteurs ────────────────────────────────
    auth_result = await db.execute(
        select(AuthorAlert).where(AuthorAlert.is_active == True)
    )
    for alert in auth_result.scalars().all():
        matched = any(alert.author_name.lower() in a.lower() for a in auteurs)
        if not matched:
            continue

        notif = Notification(
            user_id=alert.user_id,
            type="author",
            titre=f"Nouvelle publication de {alert.author_name}",
            message=article.get("titre", ""),
            pubmed_id=pubmed_id,
            is_read=False
        )
        db.add(notif)

        await _push_ws(
            user_id=str(alert.user_id),
            notification_type="author",
            titre=f"Nouvelle publication de {alert.author_name}",
            message=article.get("titre", ""),
            pubmed_id=pubmed_id,
            ws_manager=ws_manager
        )

        logger.info(f"Alerte auteur déclenchée — author='{alert.author_name}' user={alert.user_id}")

    await db.commit()


async def _push_ws(
    user_id: str,
    notification_type: str,
    titre: str,
    message: str,
    pubmed_id: str,
    ws_manager
):
    """
    Envoie un push WebSocket temps réel.
    Utilise notify_alert_triggered() du manager — méthode dédiée propre.
    Ignoré silencieusement si l'utilisateur est hors ligne.
    """
    try:
        await ws_manager.notify_alert_triggered(
            user_id=user_id,
            notification_type=notification_type,
            titre=titre,
            message=message,
            pubmed_id=pubmed_id,
        )
    except Exception as e:
        logger.warning(f"WebSocket push ignoré (user hors ligne ?) : {e}")


# ============================================================
# 📬 NOTIFICATIONS
# ============================================================

async def get_notifications(
    user_id: str,
    unread_only: bool = False,
    db: AsyncSession = None
) -> dict:
    """Récupère les notifications d'un utilisateur (50 max, triées par date)."""
    uid = uuid.UUID(user_id)

    conditions = [Notification.user_id == uid]
    if unread_only:
        conditions.append(Notification.is_read == False)

    result = await db.execute(
        select(Notification)
        .where(*conditions)
        .order_by(Notification.created_at.desc())
        .limit(50)
    )
    notifications = result.scalars().all()

    return {
        "total":  len(notifications),
        "unread": sum(1 for n in notifications if not n.is_read),
        "notifications": [
            {
                "id":         str(n.id),
                "type":       n.type,
                "titre":      n.titre,
                "message":    n.message,
                "pubmed_id":  n.pubmed_id,
                "is_read":    n.is_read,
                "created_at": str(n.created_at),
            }
            for n in notifications
        ],
    }


async def mark_as_read(user_id: str, notification_id: str, db: AsyncSession) -> dict:
    """Marque une notification comme lue."""
    result = await db.execute(
        select(Notification).where(
            Notification.id      == uuid.UUID(notification_id),
            Notification.user_id == uuid.UUID(user_id)
        )
    )
    notif = result.scalar_one_or_none()
    if not notif:
        return {"message": "Notification non trouvée"}

    notif.is_read = True
    await db.commit()
    return {"message": "Notification marquée comme lue !"}


async def mark_all_as_read(user_id: str, db: AsyncSession) -> dict:
    """Marque TOUTES les notifications d'un utilisateur comme lues."""
    result = await db.execute(
        select(Notification).where(
            Notification.user_id == uuid.UUID(user_id),
            Notification.is_read == False
        )
    )
    notifications = result.scalars().all()
    for n in notifications:
        n.is_read = True

    await db.commit()
    return {
        "message": f"{len(notifications)} notifications marquées comme lues !",
        "count":   len(notifications),
    }


# ============================================================
# 📊 DIGEST HEBDOMADAIRE
# ============================================================

async def generate_weekly_digest(user_id: str, db: AsyncSession) -> dict:
    """
    Génère le digest hebdomadaire personnalisé.

    Logique :
    1. Récupère les Top 3 spécialités préférées (UserPreference)
    2. Cherche les articles MongoDB de la dernière semaine
       dans ces spécialités (3 articles par spécialité max)
    3. Si aucun article récent → fallback sur les 5 plus récents
    """
    from app.database.mongo_database import articles_collection

    uid = uuid.UUID(user_id)

    # Top 3 préférences
    pref_result = await db.execute(
        select(UserPreference)
        .where(UserPreference.user_id == uid)
        .order_by(UserPreference.score.desc())
        .limit(3)
    )
    preferences = pref_result.scalars().all()

    une_semaine = datetime.utcnow() - timedelta(days=7)
    fields = {"pubmed_id": 1, "titre": 1, "specialite": 1, "journal": 1, "resume_ia": 1}

    digest_articles = []

    for pref in preferences:
        cursor = articles_collection.find(
            {"specialite": pref.specialite, "scraped_at": {"$gte": une_semaine}},
            fields
        ).limit(3)

        async for a in cursor:
            a.pop("_id", None)
            digest_articles.append(a)

    # Fallback — aucun article cette semaine
    if not digest_articles:
        cursor = articles_collection.find({}, fields).sort("scraped_at", -1).limit(5)
        async for a in cursor:
            a.pop("_id", None)
            digest_articles.append(a)

    return {
        "user_id":           user_id,
        "periode":           "Dernière semaine",
        "nb_articles":       len(digest_articles),
        "specialites_suivies": [p.specialite for p in preferences],
        "articles":          digest_articles,
    }