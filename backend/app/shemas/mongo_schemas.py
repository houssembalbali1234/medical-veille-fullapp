from pydantic import BaseModel, Field
from typing import Optional, List
from datetime import datetime


class ArticleMongo(BaseModel):
    """
    Schéma complet d'un article stocké dans MongoDB.
    Contient toutes les métadonnées riches d'un article scientifique.
    """
    # Identifiants
    pubmed_id: Optional[str] = None
    doi: Optional[str] = None
    pmc_id: Optional[str] = None

    # Contenu principal
    titre: str
    titre_traduit: Optional[str] = None  # Titre traduit en français si disponible
    resume: Optional[str] = None
    resume_structure: Optional[dict] = None  # {contexte, methodes, resultats, conclusion}
    texte_complet: Optional[str] = None

    # Auteurs & Affiliations
    auteurs: Optional[List[str]] = []
    affiliations: Optional[List[str]] = []
    auteur_correspondant: Optional[str] = None

    # Classification
    specialite: Optional[str] = None
    sous_specialite: Optional[str] = None
    type_etude: Optional[str] = None  # RCT, meta-analyse, cohorte...
    mots_cles: Optional[List[str]] = []
    mesh_terms: Optional[List[str]] = []  # Termes MeSH PubMed

    # Source & Publication
    source: Optional[str] = None  # pubmed, europe_pmc, biorxiv
    journal: Optional[str] = None
    annee: Optional[str] = None
    date_publication: Optional[str] = None
    volume: Optional[str] = None
    numero: Optional[str] = None
    pages: Optional[str] = None
    url: Optional[str] = None

    # Métriques
    nb_citations: Optional[int] = 0
    impact_factor: Optional[float] = None
    score_pertinence: Optional[float] = None

    # Résumé IA (généré par Llama)
    resume_ia: Optional[str] = None
    resume_ia_genere_le: Optional[datetime] = None

    # Embeddings (vecteurs pour recherche sémantique)
    embedding: Optional[List[float]] = None  # Vecteur sentence-transformers

    # Métadonnées système
    scraped_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: Optional[datetime] = None
    est_indexe: bool = False  # Indexé dans Elasticsearch ?
    est_vectorise: bool = False  # Embedding calculé ?


class ArticleMongoResponse(BaseModel):
    """Réponse API pour un article MongoDB (sans embedding pour légèreté)"""
    id: Optional[str] = None
    pubmed_id: Optional[str] = None
    titre: str
    auteurs: Optional[List[str]] = []
    resume: Optional[str] = None
    specialite: Optional[str] = None
    type_etude: Optional[str] = None
    mots_cles: Optional[List[str]] = []
    journal: Optional[str] = None
    annee: Optional[str] = None
    source: Optional[str] = None
    url: Optional[str] = None
    resume_ia: Optional[str] = None
    nb_citations: Optional[int] = 0
    scraped_at: Optional[datetime] = None

    class Config:
        from_attributes = True


class ArticleSearchRequest(BaseModel):
    """Requête de recherche d'articles"""
    query: str
    specialite: Optional[str] = None
    type_etude: Optional[str] = None
    annee_debut: Optional[int] = None
    annee_fin: Optional[int] = None
    source: Optional[str] = None
    limite: int = 20
    page: int = 1


class ScrapingLog(BaseModel):
    """Log d'une session de scraping"""
    keyword: str
    source: str  # pubmed, europe_pmc
    nb_articles_trouves: int
    nb_articles_sauvegardes: int
    nb_doublons: int
    statut: str  # success, error, partial
    erreur: Optional[str] = None
    debut: datetime = Field(default_factory=datetime.utcnow)
    fin: Optional[datetime] = None
    duree_secondes: Optional[float] = None