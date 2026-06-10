"""
scispacy_service.py — Extraction d'entités médicales
=====================================================
Utilise scispaCy avec le modèle en_core_sci_sm pour extraire
les entités médicales des résumés d'articles scientifiques.

Entités extraites :
- Maladies et conditions médicales
- Médicaments et traitements
- Procédures médicales
- Organismes biologiques
- Gènes et protéines
"""

import logging
from typing import Optional

logger = logging.getLogger("medical_veille.scispacy")

# Chargement lazy du modèle (évite de le charger au démarrage)
_nlp = None

def get_nlp():
    """Charge le modèle scispaCy une seule fois (singleton)."""
    global _nlp
    if _nlp is None:
        try:
            import spacy
            _nlp = spacy.load("en_core_sci_sm")
            logger.info("✅ Modèle scispaCy en_core_sci_sm chargé !")
        except Exception as e:
            logger.error(f"❌ Erreur chargement scispaCy : {e}")
            _nlp = None
    return _nlp


def extract_medical_entities(text: str) -> dict:
    """
    Extrait les entités médicales d'un texte.

    Args:
        text: Texte à analyser (résumé d'article)

    Returns:
        dict avec les entités extraites par catégorie
    """
    if not text or len(text.strip()) < 10:
        return {
            "entities": [],
            "diseases": [],
            "chemicals": [],
            "genes": [],
            "summary": "Texte trop court pour l'analyse"
        }

    nlp = get_nlp()
    if nlp is None:
        return {
            "entities": [],
            "diseases": [],
            "chemicals": [],
            "genes": [],
            "error": "Modèle scispaCy non disponible"
        }

    try:
        # Limiter le texte à 10000 caractères pour éviter les timeouts
        text = text[:10000]
        doc = nlp(text)

        entities = []
        diseases = []
        chemicals = []
        genes = []

        seen = set()
        for ent in doc.ents:
            if ent.text.lower() in seen or len(ent.text) < 2:
                continue
            seen.add(ent.text.lower())

            entity = {
                "text": ent.text,
                "label": ent.label_,
                "start": ent.start_char,
                "end": ent.end_char
            }
            entities.append(entity)

            # Classifier par type
            label = ent.label_.upper()
            if label in ["DISEASE", "CONDITION", "DISORDER"]:
                diseases.append(ent.text)
            elif label in ["CHEMICAL", "DRUG", "COMPOUND"]:
                chemicals.append(ent.text)
            elif label in ["GENE", "PROTEIN", "DNA", "RNA"]:
                genes.append(ent.text)

        return {
            "entities": entities[:20],  # Limiter à 20 entités
            "diseases": diseases[:10],
            "chemicals": chemicals[:10],
            "genes": genes[:10],
            "total_entities": len(entities)
        }

    except Exception as e:
        logger.error(f"Erreur extraction entités : {e}")
        return {
            "entities": [],
            "diseases": [],
            "chemicals": [],
            "genes": [],
            "error": str(e)
        }


def extract_key_terms(text: str, max_terms: int = 10) -> list[str]:
    """
    Extrait les termes médicaux clés d'un texte.
    Utilisé pour enrichir les alertes et les recommandations.
    """
    result = extract_medical_entities(text)
    entities = result.get("entities", [])

    # Retourner les textes des entités uniques
    terms = list({e["text"] for e in entities})
    return terms[:max_terms]