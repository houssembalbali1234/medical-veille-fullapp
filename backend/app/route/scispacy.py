from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from app.services.scispacy_service import extract_medical_entities, extract_key_terms

router = APIRouter(prefix="/scispacy", tags=["scispaCy — NLP Médical"])


class TextRequest(BaseModel):
    text: str


@router.post("/extract", response_model=dict)
async def extract_entities(request: TextRequest):
    if not request.text or len(request.text.strip()) < 10:
        raise HTTPException(status_code=400, detail="Texte trop court")
    result = extract_medical_entities(request.text)
    return {"status": "ok", "text_length": len(request.text), **result}


@router.post("/keywords", response_model=dict)
async def extract_keywords(request: TextRequest):
    terms = extract_key_terms(request.text)
    return {"status": "ok", "keywords": terms, "total": len(terms)}


@router.get("/health", response_model=dict)
async def scispacy_health():
    from app.services.scispacy_service import get_nlp
    nlp = get_nlp()
    return {"status": "ok" if nlp else "error", "model": "en_core_sci_sm", "loaded": nlp is not None}