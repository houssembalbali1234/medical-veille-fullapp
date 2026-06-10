import os
from groq import Groq
from typing import Optional

# ============================================================
# ⚙️ CONFIGURATION
# ============================================================

GROQ_API_KEY = os.getenv("GROQ_API_KEY", "")
MODEL = "llama-3.1-8b-instant"

_client: Optional[Groq] = None


def get_groq_client() -> Groq:
    global _client
    if _client is None:
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY non configurée !")
        _client = Groq(api_key=GROQ_API_KEY)
        print(f"✅ Groq (Llama 3.1) connecté !")
    return _client


# ============================================================
# 🧠 GÉNÉRATION DE RÉSUMÉS
# ============================================================

def generate_resume_ia(article: dict) -> dict:
    client = get_groq_client()

    titre = article.get("titre", "")
    resume = article.get("resume", "")
    journal = article.get("journal", "")
    annee = article.get("annee", "")
    type_etude = article.get("type_etude", "")
    specialite = article.get("specialite", "")

    if not resume or len(resume) < 50:
        return {
            "resume_ia": "Résumé original insuffisant pour générer un résumé IA.",
            "population": None,
            "intervention": None,
            "resultats": None,
            "conclusion": None,
            "mots": 0
        }

    prompt = f"""Tu es un assistant médical expert. Analyse cet article scientifique et génère un résumé structuré en français pour des professionnels de santé.

ARTICLE :
Titre : {titre}
Journal : {journal} ({annee})
Type d'étude : {type_etude}
Spécialité : {specialite}
Résumé original : {resume[:2000]}

INSTRUCTIONS :
Génère un résumé structuré en JSON avec exactement ces champs :
- "population" : qui a été étudié (patients, age, critères)
- "intervention" : traitement ou intervention principale
- "resultats" : résultats principaux avec chiffres clés
- "conclusion" : conclusion clinique pratique
- "resume_court" : résumé global en 2-3 phrases maximum (<100 mots)

Réponds UNIQUEMENT avec le JSON, sans texte avant ou après.
Format exact :
{{
  "population": "...",
  "intervention": "...",
  "resultats": "...",
  "conclusion": "...",
  "resume_court": "..."
}}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.3,
            max_tokens=500
        )

        content = response.choices[0].message.content.strip()

        import json
        if "```json" in content:
            content = content.split("```json")[1].split("```")[0].strip()
        elif "```" in content:
            content = content.split("```")[1].split("```")[0].strip()

        parsed = json.loads(content)
        resume_ia = parsed.get("resume_court", "")
        nb_mots = len(resume_ia.split())

        return {
            "resume_ia": resume_ia,
            "population": parsed.get("population"),
            "intervention": parsed.get("intervention"),
            "resultats": parsed.get("resultats"),
            "conclusion": parsed.get("conclusion"),
            "mots": nb_mots
        }

    except Exception as e:
        print(f"⚠️ Erreur Groq: {e}")
        return {
            "resume_ia": f"Erreur génération résumé: {str(e)}",
            "population": None,
            "intervention": None,
            "resultats": None,
            "conclusion": None,
            "mots": 0
        }


# ============================================================
# 🇫🇷 TRADUCTION EN FRANÇAIS
# ============================================================

def translate_to_french(text: str) -> str:
    """
    Traduit un texte médical anglais en français via Llama 3.1.
    Traduction fidèle et complète, sans résumer.
    """
    client = get_groq_client()

    if not text or len(text) < 10:
        return text

    prompt = f"""Traduis ce texte médical en français.
Traduction complète et fidèle mot à mot, sans résumer, sans modifier le sens.
Réponds UNIQUEMENT avec la traduction en français, rien d'autre.

Texte à traduire:
{text}"""

    try:
        response = client.chat.completions.create(
            model=MODEL,
            messages=[{"role": "user", "content": prompt}],
            temperature=0.1,
            max_tokens=1000
        )
        return response.choices[0].message.content.strip()
    except Exception as e:
        print(f"⚠️ Erreur traduction: {e}")
        return text


async def generate_resume_for_article(pubmed_id: str, db) -> dict:
    from app.database.mongo_database import articles_collection

    article = await articles_collection.find_one({"pubmed_id": pubmed_id})
    if not article:
        raise ValueError(f"Article {pubmed_id} non trouvé")

    if article.get("resume_ia"):
        return {
            "message": "Résumé déjà généré",
            "resume_ia": article["resume_ia"],
            "pubmed_id": pubmed_id
        }

    result = generate_resume_ia(article)

    await articles_collection.update_one(
        {"pubmed_id": pubmed_id},
        {"$set": {
            "resume_ia": result["resume_ia"],
            "resume_structure": {
                "population": result["population"],
                "intervention": result["intervention"],
                "resultats": result["resultats"],
                "conclusion": result["conclusion"],
            }
        }}
    )

    return {
        "message": "✅ Résumé généré !",
        "pubmed_id": pubmed_id,
        **result
    }


async def generate_resumes_bulk(limit: int = 10) -> dict:
    from app.database.mongo_database import articles_collection

    cursor = articles_collection.find(
        {
            "resume_ia": None,
            "resume": {"$ne": "", "$ne": None}
        },
        {"pubmed_id": 1, "titre": 1, "resume": 1,
         "journal": 1, "annee": 1, "type_etude": 1, "specialite": 1}
    ).limit(limit)

    articles = await cursor.to_list(length=limit)

    if not articles:
        return {"message": "Tous les articles ont déjà un résumé IA !", "generated": 0}

    nb_generated = 0
    errors = 0

    for article in articles:
        try:
            pubmed_id = article.get("pubmed_id")
            if not pubmed_id:
                continue

            result = generate_resume_ia(article)

            await articles_collection.update_one(
                {"pubmed_id": pubmed_id},
                {"$set": {
                    "resume_ia": result["resume_ia"],
                    "resume_structure": {
                        "population": result["population"],
                        "intervention": result["intervention"],
                        "resultats": result["resultats"],
                        "conclusion": result["conclusion"],
                    }
                }}
            )
            nb_generated += 1
            print(f"✅ Résumé généré pour {pubmed_id} ({nb_generated}/{len(articles)})")

        except Exception as e:
            print(f"⚠️ Erreur résumé {article.get('pubmed_id')}: {e}")
            errors += 1
            continue

    return {
        "message": f"✅ {nb_generated} résumés générés !",
        "generated": nb_generated,
        "errors": errors,
        "total_processed": len(articles)
    }