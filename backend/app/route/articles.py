from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from typing import List

from app.database.database import get_db
from app.models import Article, User
from app.shemas.schemas import ArticleCreate, ArticleResponse
from app.auth import get_current_user
from app.services.pubmed_service import search_and_fetch
from app.services.pipeline_service import process_article

router = APIRouter(prefix="/articles-pg", tags=["Articles PostgreSQL"])


@router.post("/", response_model=ArticleResponse, status_code=201)
async def create_article(
    data: ArticleCreate,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    article = Article(**data.model_dump())
    db.add(article)
    await db.commit()
    await db.refresh(article)
    return article


@router.post("/scrape-and-process", status_code=201)
async def scrape_and_process(
    q: str = Query("cancer"),
    max_results: int = Query(5, le=20),
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    pubmed_articles = search_and_fetch(query=q, max_results=max_results)
    if not pubmed_articles:
        raise HTTPException(status_code=404, detail=f"Aucun article PubMed trouvé pour '{q}'")

    created = []
    skipped = 0
    ai_errors = 0

    for art in pubmed_articles:
        existing = await db.execute(select(Article).where(Article.pubmed_id == art["pubmed_id"]))
        if existing.scalar_one_or_none():
            skipped += 1
            continue
        try:
            ai_result = process_article(art)
        except Exception:
            ai_result = {"specialite": "General", "type_etude": "Non specifie", "resume_ia": None}
            ai_errors += 1

        new_article = Article(
            titre=art["titre"],
            auteurs=", ".join(art["auteurs"]) if art["auteurs"] else None,
            resume=art["resume"],
            specialite=ai_result.get("specialite"),
            source=art["source"],
            pubmed_id=art["pubmed_id"],
            annee=art["annee"],
        )
        db.add(new_article)
        await db.commit()
        await db.refresh(new_article)
        created.append({
            "pubmed_id": art["pubmed_id"],
            "titre": art["titre"],
            "specialite": ai_result.get("specialite"),
            "type_etude": ai_result.get("type_etude"),
            "resume_ia": ai_result.get("resume_ia"),
        })

    return {"query": q, "found": len(pubmed_articles), "created": len(created), "skipped": skipped, "ai_errors": ai_errors, "articles": created}


@router.post("/{article_id}/process")
async def process_existing_article(
    article_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article non trouvé")

    article_dict = {"titre": article.titre, "resume": article.resume or "", "auteurs": article.auteurs or "", "journal": "", "annee": article.annee or ""}
    ai_result = process_article(article_dict)
    article.specialite = ai_result.get("specialite")
    await db.commit()
    return {"article_id": article_id, "titre": article.titre, **ai_result}


@router.post("/{article_id}/translate")
async def translate_article(
    article_id: str,
    db: AsyncSession = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    from app.services.llama_service import translate_to_french
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article non trouvé")

    titre_fr = translate_to_french(article.titre) if article.titre else ""
    resume_fr = translate_to_french(article.resume) if article.resume else ""
    return {"article_id": article_id, "titre_fr": titre_fr, "resume_fr": resume_fr}


@router.get("/", response_model=List[ArticleResponse])
async def get_articles(db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Article).order_by(Article.created_at.desc()))
    return result.scalars().all()


@router.get("/search", response_model=List[ArticleResponse])
async def search_articles_db(
    keyword: str = Query(...),
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(select(Article).where(Article.titre.ilike(f"%{keyword}%")))
    return result.scalars().all()


# ✅ Nouvelle route — chercher par pubmed_id
@router.get("/by-pubmed/{pubmed_id}", response_model=ArticleResponse)
async def get_article_by_pubmed_id(
    pubmed_id: str,
    db: AsyncSession = Depends(get_db)
):
    """Récupérer un article PostgreSQL par son pubmed_id"""
    result = await db.execute(select(Article).where(Article.pubmed_id == pubmed_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article non trouvé")
    return article


@router.get("/{article_id}", response_model=ArticleResponse)
async def get_article(article_id: str, db: AsyncSession = Depends(get_db)):
    result = await db.execute(select(Article).where(Article.id == article_id))
    article = result.scalar_one_or_none()
    if not article:
        raise HTTPException(status_code=404, detail="Article non trouvé")
    return article