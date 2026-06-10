# app/services/pipeline_service.py
"""
Pipeline Service — Orchestrateur IA
=====================================
Connecte les différents services IA dans un workflow complet :

    article dict
        ↓
    classify_article()     → spécialité + type d'étude
        ↓
    generate_resume_ia()   → résumé structuré Llama 3.1
        ↓
    résultat enrichi

Utilisé par routes/articles.py pour enrichir les articles
importés depuis PubMed avant de les sauvegarder.
"""

import logging
from app.services.classifier import classify_article
from app.services.llama_service import generate_resume_ia

logger = logging.getLogger("medical_veille.pipeline")


def process_article(article: dict) -> dict:
    """
    Traite un article avec le pipeline IA complet.

    Args:
        article : dict avec au minimum les clés :
                  - titre
                  - resume  (résumé original)
                  - auteurs (optionnel)
                  - journal (optionnel)
                  - annee   (optionnel)

    Returns:
        dict avec les clés ajoutées :
        - specialite       : spécialité médicale détectée
        - type_etude       : type d'étude détecté (RCT, méta-analyse...)
        - resume_ia        : résumé structuré généré par Llama
        - resume_structure : {population, intervention, resultats, conclusion}
    """
    result = {
        "specialite":       None,
        "type_etude":       None,
        "resume_ia":        None,
        "resume_structure": None,
    }

    # ── Étape 1 : Classification ──────────────────────────
    try:
        classification = classify_article(article)
        result["specialite"] = classification.get("specialite", "Général")
        result["type_etude"] = classification.get("type_etude", "Non spécifié")
        logger.info(
            f"Classification OK — "
            f"specialite={result['specialite']} "
            f"type={result['type_etude']}"
        )
    except Exception as e:
        logger.warning(f"Erreur classification : {e}")
        result["specialite"] = "Général"
        result["type_etude"] = "Non spécifié"

    # ── Étape 2 : Résumé IA (Llama via Groq) ─────────────
    # On enrichit l'article avec la classification avant de générer le résumé
    # pour que Llama ait le contexte complet (spécialité + type d'étude)
    enriched = {**article, **result}

    try:
        resume_result = generate_resume_ia(enriched)
        result["resume_ia"]        = resume_result.get("resume_ia")
        result["resume_structure"] = {
            "population":  resume_result.get("population"),
            "intervention": resume_result.get("intervention"),
            "resultats":   resume_result.get("resultats"),
            "conclusion":  resume_result.get("conclusion"),
        }
        logger.info(
            f"Résumé IA généré — "
            f"{resume_result.get('mots', 0)} mots"
        )
    except Exception as e:
        logger.warning(f"Erreur génération résumé IA : {e}")
        result["resume_ia"] = None

    return result


def process_articles_bulk(articles: list[dict]) -> list[dict]:
    """
    Traite une liste d'articles avec le pipeline IA.
    Continue même si un article échoue.

    Returns:
        Liste des articles enrichis avec specialite, type_etude, resume_ia
    """
    enriched = []

    for i, article in enumerate(articles):
        try:
            ai_result = process_article(article)
            enriched.append({**article, **ai_result})
            logger.info(f"Pipeline OK ({i+1}/{len(articles)}) — {article.get('titre', '')[:50]}")
        except Exception as e:
            logger.error(f"Pipeline échoué pour article {i+1} : {e}")
            enriched.append(article)  # On garde l'article sans enrichissement

    return enriched