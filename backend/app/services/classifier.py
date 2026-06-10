import numpy as np
from typing import Optional

# ============================================================
# ⚙️ CONFIGURATION — Spécialités médicales
# ============================================================

# Chaque spécialité est définie par des phrases représentatives
# Le modèle PubMedBert va comparer l'article avec ces phrases
# et choisir la spécialité la plus proche sémantiquement

SPECIALITES = {
    "Cardiologie": [
        "heart disease cardiac cardiovascular hypertension",
        "myocardial infarction heart failure arrhythmia",
        "coronary artery disease stroke blood pressure"
    ],
    "Oncologie": [
        "cancer tumor malignant oncology chemotherapy",
        "breast cancer lung cancer colorectal cancer",
        "carcinoma metastasis radiotherapy immunotherapy"
    ],
    "Endocrinologie": [
        "diabetes insulin hormone thyroid endocrine",
        "diabetes mellitus glucose obesity metabolic syndrome",
        "thyroid disease adrenal gland pituitary hormone"
    ],
    "Neurologie": [
        "brain neurology stroke alzheimer parkinson",
        "multiple sclerosis epilepsy dementia neurodegenerative",
        "nervous system cognitive decline neurological disorder"
    ],
    "Néphrologie": [
        "kidney renal nephrology chronic kidney disease",
        "renal failure dialysis transplant glomerulonephritis",
        "kidney function creatinine proteinuria urinary"
    ],
    "Pneumologie": [
        "lung respiratory pulmonary asthma COPD",
        "pneumonia bronchitis respiratory failure oxygen",
        "chronic obstructive pulmonary disease breathing"
    ],
    "Gastroentérologie": [
        "liver digestive gastrointestinal hepatitis cirrhosis",
        "inflammatory bowel disease crohn colitis gastric",
        "colon intestine pancreas bile acid reflux"
    ],
    "Immunologie": [
        "immune system autoimmune inflammation cytokine",
        "rheumatoid arthritis lupus immunodeficiency allergy",
        "T cell B cell antibody vaccination immunotherapy"
    ],
    "Infectiologie": [
        "infection bacterial viral antibiotic antimicrobial",
        "COVID-19 HIV tuberculosis sepsis pneumonia",
        "pathogen vaccine infectious disease antimicrobial resistance"
    ],
    "Général": [
        "general medicine clinical practice patient care",
        "public health epidemiology prevention screening",
        "clinical trial randomized controlled study"
    ]
}

# Types d'études médicales avec leurs mots-clés
TYPES_ETUDE = {
    "Essai clinique randomisé (RCT)": [
        "randomized controlled trial RCT placebo double blind",
        "random assignment treatment control group clinical trial"
    ],
    "Méta-analyse": [
        "meta-analysis systematic review pooled analysis",
        "literature review evidence synthesis meta-analysis"
    ],
    "Étude de cohorte": [
        "cohort study longitudinal prospective retrospective follow-up",
        "observational study cohort population based"
    ],
    "Étude cas-témoins": [
        "case control study odds ratio risk factor",
        "case study matched controls exposure outcome"
    ],
    "Revue systématique": [
        "systematic review literature search evidence based",
        "comprehensive review PRISMA guidelines review article"
    ],
    "Étude transversale": [
        "cross sectional study prevalence survey population",
        "cross-sectional epidemiological study point prevalence"
    ],
    "Rapport de cas": [
        "case report single patient clinical case presentation",
        "case series individual patient unusual presentation"
    ],
    "Étude expérimentale": [
        "in vitro in vivo animal model laboratory experiment",
        "cell culture mouse model preclinical experimental study"
    ],
    "Non spécifié": [
        "study research analysis investigation"
    ]
}


# ============================================================
# 🧠 CLASSIFICATION PAR SPÉCIALITÉ
# ============================================================

def classify_specialite(article: dict) -> str:
    """
    Classifie un article dans une spécialité médicale.
    
    Méthode Zero-Shot avec similarité cosinus :
    1. On vectorise le texte de l'article
    2. On vectorise les phrases représentatives de chaque spécialité
    3. On calcule la similarité cosinus entre l'article et chaque spécialité
    4. On retourne la spécialité avec le score le plus élevé
    
    Avantage : pas besoin d'entraîner un modèle !
    PubMedBert comprend déjà le vocabulaire médical.
    """
    from app.database.qdrant_database import embedding_model, build_article_text

    if embedding_model is None:
        return "Général"

    # 1. Construire et vectoriser le texte de l'article
    text = build_article_text(article)
    if not text.strip():
        return "Général"

    article_vector = embedding_model.encode(text, normalize_embeddings=True)

    # 2. Calculer la similarité avec chaque spécialité
    best_specialite = "Général"
    best_score = -1.0

    for specialite, phrases in SPECIALITES.items():
        # Vectoriser toutes les phrases de cette spécialité
        phrase_vectors = embedding_model.encode(phrases, normalize_embeddings=True)
        
        # Score = moyenne des similarités cosinus avec toutes les phrases
        scores = np.dot(phrase_vectors, article_vector)
        avg_score = float(np.mean(scores))

        if avg_score > best_score:
            best_score = avg_score
            best_specialite = specialite

    return best_specialite


def classify_type_etude(article: dict) -> str:
    """
    Détecte le type d'étude d'un article médical.
    
    Même méthode que classify_specialite mais pour les types d'études.
    Analyse principalement le titre et le résumé.
    """
    from app.database.qdrant_database import embedding_model

    if embedding_model is None:
        return "Non spécifié"

    # Pour le type d'étude, on utilise surtout le titre + résumé
    text_parts = []
    if article.get("titre"):
        text_parts.append(article["titre"])
    if article.get("resume"):
        # On prend les 500 premiers caractères du résumé (suffisant)
        text_parts.append(article["resume"][:500])

    text = " ".join(text_parts)
    if not text.strip():
        return "Non spécifié"

    article_vector = embedding_model.encode(text, normalize_embeddings=True)

    best_type = "Non spécifié"
    best_score = -1.0

    for type_etude, phrases in TYPES_ETUDE.items():
        phrase_vectors = embedding_model.encode(phrases, normalize_embeddings=True)
        scores = np.dot(phrase_vectors, article_vector)
        avg_score = float(np.mean(scores))

        if avg_score > best_score:
            best_score = avg_score
            best_type = type_etude

    return best_type


def classify_article(article: dict) -> dict:
    """
    Classifie un article complet (spécialité + type d'étude).
    Retourne un dict avec les deux classifications.
    """
    specialite = classify_specialite(article)
    type_etude = classify_type_etude(article)
    
    return {
        "specialite": specialite,
        "type_etude": type_etude
    }


# ============================================================
# 🔄 CLASSIFICATION EN MASSE
# ============================================================

async def classify_all_articles() -> dict:
    """
    Classifie tous les articles non classifiés dans MongoDB.
    Met à jour les champs specialite et type_etude.
    """
    from app.database.mongo_database import articles_collection

    # Récupérer les articles sans spécialité
    cursor = articles_collection.find(
        {"specialite": None},
        {"pubmed_id": 1, "titre": 1, "resume": 1, "mots_cles": 1}
    )
    articles = await cursor.to_list(length=None)

    if not articles:
        return {"message": "Tous les articles sont déjà classifiés !", "classified": 0}

    nb_classified = 0
    print(f"⏳ Classification de {len(articles)} articles...")

    for article in articles:
        try:
            result = classify_article(article)

            # Mettre à jour dans MongoDB
            await articles_collection.update_one(
                {"pubmed_id": article["pubmed_id"]},
                {"$set": {
                    "specialite": result["specialite"],
                    "type_etude": result["type_etude"]
                }}
            )
            nb_classified += 1

            if nb_classified % 10 == 0:
                print(f"✅ {nb_classified}/{len(articles)} articles classifiés...")

        except Exception as e:
            print(f"⚠️ Erreur classification article {article.get('pubmed_id')}: {e}")
            continue

    print(f"✅ Classification terminée ! {nb_classified} articles classifiés.")
    return {
        "message": f"✅ {nb_classified} articles classifiés !",
        "classified": nb_classified,
        "total": len(articles)
    }