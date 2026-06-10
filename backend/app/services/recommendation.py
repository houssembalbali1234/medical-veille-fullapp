import uuid
from typing import Optional
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from app.models import UserInteraction, UserPreference, SavedArticle

# ============================================================
# CONFIGURATION — Poids des interactions
# ============================================================

INTERACTION_WEIGHTS = {
    "view": 1.0,
    "like": 3.0,
    "save": 2.0,
    "share": 2.5,
    "dislike": -2.0
}


# ============================================================
# ENREGISTREMENT DES INTERACTIONS
# ============================================================

async def record_interaction(
    user_id: str,
    pubmed_id: str,
    interaction_type: str,
    specialite: Optional[str],
    db: AsyncSession
) -> dict:
    if interaction_type not in INTERACTION_WEIGHTS:
        raise ValueError(f"Type d'interaction invalide: {interaction_type}")

    score = INTERACTION_WEIGHTS[interaction_type]

    interaction = UserInteraction(
        user_id=uuid.UUID(user_id),
        pubmed_id=pubmed_id,
        interaction_type=interaction_type,
        specialite=specialite,
        score=score
    )
    db.add(interaction)

    if specialite:
        await _update_preference(user_id, specialite, score, db)

    await db.commit()

    return {
        "message": "✅ Interaction enregistrée !",
        "user_id": user_id,
        "pubmed_id": pubmed_id,
        "interaction_type": interaction_type,
        "score": score
    }


async def _update_preference(
    user_id: str,
    specialite: str,
    score: float,
    db: AsyncSession
):
    result = await db.execute(
        select(UserPreference).where(
            UserPreference.user_id == uuid.UUID(user_id),
            UserPreference.specialite == specialite
        )
    )
    preference = result.scalar_one_or_none()

    if preference:
        preference.score += score
        preference.nb_interactions += 1
    else:
        preference = UserPreference(
            user_id=uuid.UUID(user_id),
            specialite=specialite,
            score=score,
            nb_interactions=1
        )
        db.add(preference)


# ============================================================
# ALGORITHME DE RECOMMANDATION HYBRIDE
# ============================================================

async def get_recommendations(
    user_id: str,
    limit: int = 10,
    db: AsyncSession = None
) -> list[dict]:
    from app.database.mongo_database import articles_collection
    from app.database.qdrant_database import search_similar

    preferences = await _get_user_preferences(user_id, db)
    seen_ids = await _get_seen_articles(user_id, db)

    recommendations = []

    if preferences:
        top_specialites = sorted(
            preferences.items(),
            key=lambda x: x[1],
            reverse=True
        )[:3]

        for specialite, pref_score in top_specialites:
            if pref_score <= 0:
                continue

            # ✅ Fix: ignorer le filtre spécialité si c'est "Général" ou null
            # car les articles dans Qdrant ont specialite=null
            specialite_filter = None  # Toujours None car articles ont specialite=null dans Qdrant

            try:
                results = await search_similar(
                    query=f"medical research {specialite}",
                    specialite=specialite_filter,
                    limit=limit // max(len(top_specialites), 1) + 2,
                    score_threshold=0.2
                )
            except Exception as e:
                print(f"⚠️ Erreur Qdrant pour {specialite}: {e}")
                results = []

            for article in results:
                pubmed_id = article.get("pubmed_id", "")
                if pubmed_id not in seen_ids:
                    article["recommendation_score"] = round(
                        article.get("similarity_score", 0) * pref_score, 4
                    )
                    article["recommendation_reason"] = f"Basé sur votre intérêt pour {specialite}"
                    recommendations.append(article)

    # ✅ Fix: si pas de recommandations via Qdrant → articles populaires
    if not recommendations:
        recommendations = await _get_popular_articles(limit, db)

    # Dédupliquer et trier
    seen = set()
    unique_recs = []
    for rec in recommendations:
        pid = rec.get("pubmed_id", "")
        if pid and pid not in seen and pid not in seen_ids:
            seen.add(pid)
            unique_recs.append(rec)

    unique_recs.sort(
        key=lambda x: x.get("recommendation_score", 0),
        reverse=True
    )

    return unique_recs[:limit]


async def _get_user_preferences(user_id: str, db: AsyncSession) -> dict:
    result = await db.execute(
        select(UserPreference).where(
            UserPreference.user_id == uuid.UUID(user_id)
        )
    )
    preferences = result.scalars().all()
    return {p.specialite: p.score for p in preferences}


async def _get_seen_articles(user_id: str, db: AsyncSession) -> set:
    result = await db.execute(
        select(UserInteraction.pubmed_id).where(
            UserInteraction.user_id == uuid.UUID(user_id)
        )
    )
    return {row[0] for row in result.fetchall()}


async def _get_popular_articles(limit: int, db: AsyncSession) -> list[dict]:
    from app.database.mongo_database import articles_collection

    cursor = articles_collection.find(
        {"resume_ia": {"$ne": None}},
        {"pubmed_id": 1, "titre": 1, "specialite": 1,
         "journal": 1, "annee": 1, "resume_ia": 1}
    ).sort("scraped_at", -1).limit(limit)

    articles = await cursor.to_list(length=limit)
    result = []
    for a in articles:
        a.pop("_id", None)
        a["recommendation_score"] = 1.0
        a["recommendation_reason"] = "Article récent populaire"
        result.append(a)
    return result


# ============================================================
# ARTICLES SAUVEGARDÉS
# ============================================================

async def save_article(
    user_id: str,
    pubmed_id: str,
    titre: str,
    specialite: Optional[str],
    note: Optional[str],
    db: AsyncSession
) -> dict:
    result = await db.execute(
        select(SavedArticle).where(
            SavedArticle.user_id == uuid.UUID(user_id),
            SavedArticle.pubmed_id == pubmed_id
        )
    )
    existing = result.scalar_one_or_none()

    if existing:
        return {"message": "Article déjà sauvegardé", "pubmed_id": pubmed_id}

    saved = SavedArticle(
        user_id=uuid.UUID(user_id),
        pubmed_id=pubmed_id,
        titre=titre,
        specialite=specialite,
        note=note
    )
    db.add(saved)

    await record_interaction(user_id, pubmed_id, "save", specialite, db)

    return {
        "message": "✅ Article sauvegardé !",
        "pubmed_id": pubmed_id,
        "titre": titre
    }


async def get_saved_articles(user_id: str, db: AsyncSession) -> list[dict]:
    result = await db.execute(
        select(SavedArticle).where(
            SavedArticle.user_id == uuid.UUID(user_id)
        ).order_by(SavedArticle.saved_at.desc())
    )
    saved = result.scalars().all()
    return [
        {
            "pubmed_id": s.pubmed_id,
            "titre": s.titre,
            "specialite": s.specialite,
            "note": s.note,
            "saved_at": str(s.saved_at)
        }
        for s in saved
    ]


async def get_user_stats(user_id: str, db: AsyncSession) -> dict:
    result = await db.execute(
        select(UserInteraction).where(
            UserInteraction.user_id == uuid.UUID(user_id)
        )
    )
    interactions = result.scalars().all()

    preferences = await _get_user_preferences(user_id, db)
    saved = await get_saved_articles(user_id, db)

    return {
        "total_interactions": len(interactions),
        "interactions_par_type": {
            t: len([i for i in interactions if i.interaction_type == t])
            for t in INTERACTION_WEIGHTS.keys()
        },
        "specialites_preferees": dict(
            sorted(preferences.items(), key=lambda x: x[1], reverse=True)[:5]
        ),
        "articles_sauvegardes": len(saved)
    }