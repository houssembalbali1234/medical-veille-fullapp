from typing import Optional
from itertools import combinations

# ============================================================
# 🔬 SERVICE RÉSEAU DE COLLABORATION
# ============================================================

async def get_researcher_profile(author_name: str) -> dict:
    """
    Retourne le profil complet d'un chercheur :
    - Articles publiés
    - Co-auteurs
    - Spécialités
    - Journaux
    """
    from app.database.mongo_database import articles_collection

    # Chercher tous les articles de cet auteur
    cursor = articles_collection.find(
        {"auteurs": {"$regex": author_name, "$options": "i"}},
        {"pubmed_id": 1, "titre": 1, "auteurs": 1, "specialite": 1,
         "journal": 1, "annee": 1, "resume_ia": 1}
    )
    articles = await cursor.to_list(length=100)

    if not articles:
        return {"error": f"Chercheur '{author_name}' non trouvé"}

    # Extraire les co-auteurs
    coauthors = {}
    specialites = {}
    journaux = {}
    annees = []

    for article in articles:
        # Co-auteurs
        for auteur in article.get("auteurs", []):
            if author_name.lower() not in auteur.lower():
                coauthors[auteur] = coauthors.get(auteur, 0) + 1

        # Spécialités
        spec = article.get("specialite")
        if spec:
            specialites[spec] = specialites.get(spec, 0) + 1

        # Journaux
        journal = article.get("journal", "")
        if journal:
            journaux[journal] = journaux.get(journal, 0) + 1

        # Années
        annee = article.get("annee", "")
        if annee:
            annees.append(annee)

    # Trier les co-auteurs par nombre de collaborations
    top_coauthors = sorted(
        [{"nom": k, "nb_collaborations": v} for k, v in coauthors.items()],
        key=lambda x: x["nb_collaborations"],
        reverse=True
    )[:10]

    return {
        "nom": author_name,
        "nb_articles": len(articles),
        "specialites": dict(sorted(specialites.items(), key=lambda x: x[1], reverse=True)),
        "top_journaux": dict(sorted(journaux.items(), key=lambda x: x[1], reverse=True)[:5]),
        "annees_actif": sorted(set(annees), reverse=True)[:5],
        "top_coauthors": top_coauthors,
        "articles": [
            {
                "pubmed_id": a.get("pubmed_id"),
                "titre": a.get("titre"),
                "annee": a.get("annee"),
                "specialite": a.get("specialite")
            }
            for a in articles[:10]
        ]
    }


async def get_collaboration_graph(specialite: Optional[str] = None, limit: int = 50) -> dict:
    """
    Construit le graphe de co-auteurs depuis MongoDB.
    
    Retourne :
    - nodes : liste des chercheurs
    - edges : liens entre co-auteurs (avec poids)
    
    Utilisé pour visualiser le réseau de collaboration.
    """
    from app.database.mongo_database import articles_collection

    # Filtre optionnel par spécialité
    filtre = {}
    if specialite:
        filtre["specialite"] = specialite

    cursor = articles_collection.find(
        filtre,
        {"auteurs": 1, "specialite": 1, "pubmed_id": 1}
    ).limit(limit)
    articles = await cursor.to_list(length=limit)

    nodes = {}
    edges = {}

    for article in articles:
        auteurs = article.get("auteurs", [])
        spec = article.get("specialite", "Général")

        # Ajouter les noeuds
        for auteur in auteurs:
            if auteur not in nodes:
                nodes[auteur] = {
                    "id": auteur,
                    "label": auteur,
                    "specialite": spec,
                    "nb_articles": 0
                }
            nodes[auteur]["nb_articles"] += 1

        # Ajouter les liens entre co-auteurs
        for auteur1, auteur2 in combinations(auteurs, 2):
            edge_key = tuple(sorted([auteur1, auteur2]))
            if edge_key not in edges:
                edges[edge_key] = {
                    "source": auteur1,
                    "target": auteur2,
                    "weight": 0
                }
            edges[edge_key]["weight"] += 1

    return {
        "nodes": list(nodes.values()),
        "edges": list(edges.values()),
        "total_researchers": len(nodes),
        "total_collaborations": len(edges)
    }


async def get_collaboration_suggestions(author_name: str, limit: int = 5) -> dict:
    """
    Suggère des collaborateurs potentiels pour un chercheur.
    
    Algorithme :
    1. Trouve les co-auteurs des co-auteurs (amis d'amis)
    2. Filtre ceux qui partagent la même spécialité
    3. Trie par nombre de connexions communes
    """
    from app.database.mongo_database import articles_collection

    # Trouver les co-auteurs directs
    cursor = articles_collection.find(
        {"auteurs": {"$regex": author_name, "$options": "i"}},
        {"auteurs": 1, "specialite": 1}
    )
    articles = await cursor.to_list(length=100)

    if not articles:
        return {"error": f"Chercheur '{author_name}' non trouvé"}

    # Co-auteurs directs
    direct_coauthors = set()
    specialites = []

    for article in articles:
        spec = article.get("specialite")
        if spec:
            specialites.append(spec)
        for auteur in article.get("auteurs", []):
            if author_name.lower() not in auteur.lower():
                direct_coauthors.add(auteur)

    # Spécialité principale
    main_specialite = max(set(specialites), key=specialites.count) if specialites else None

    # Trouver les co-auteurs des co-auteurs
    suggestions = {}
    for coauthor in list(direct_coauthors)[:20]:
        cursor2 = articles_collection.find(
            {"auteurs": {"$regex": coauthor, "$options": "i"}},
            {"auteurs": 1, "specialite": 1}
        )
        coauthor_articles = await cursor2.to_list(length=50)

        for article in coauthor_articles:
            for auteur in article.get("auteurs", []):
                # Exclure l'auteur lui-même et ses co-auteurs directs
                if (author_name.lower() not in auteur.lower() and
                        auteur not in direct_coauthors):
                    if auteur not in suggestions:
                        suggestions[auteur] = {
                            "nom": auteur,
                            "connexions_communes": 0,
                            "specialite": article.get("specialite"),
                            "via": []
                        }
                    suggestions[auteur]["connexions_communes"] += 1
                    if coauthor not in suggestions[auteur]["via"]:
                        suggestions[auteur]["via"].append(coauthor)

    # Trier par connexions communes
    top_suggestions = sorted(
        suggestions.values(),
        key=lambda x: x["connexions_communes"],
        reverse=True
    )[:limit]

    return {
        "chercheur": author_name,
        "specialite_principale": main_specialite,
        "nb_coauthors_directs": len(direct_coauthors),
        "suggestions": top_suggestions
    }


async def get_top_researchers(specialite: Optional[str] = None, limit: int = 10) -> list:
    """
    Retourne les chercheurs les plus prolifiques.
    Classés par nombre d'articles publiés.
    """
    from app.database.mongo_database import articles_collection

    filtre = {}
    if specialite:
        filtre["specialite"] = specialite

    cursor = articles_collection.find(filtre, {"auteurs": 1, "specialite": 1})
    articles = await cursor.to_list(length=1000)

    researchers = {}
    for article in articles:
        for auteur in article.get("auteurs", []):
            if auteur not in researchers:
                researchers[auteur] = {
                    "nom": auteur,
                    "nb_articles": 0,
                    "specialites": {}
                }
            researchers[auteur]["nb_articles"] += 1
            spec = article.get("specialite", "Général")
            researchers[auteur]["specialites"][spec] = \
                researchers[auteur]["specialites"].get(spec, 0) + 1

    # Trier par nombre d'articles
    top = sorted(
        researchers.values(),
        key=lambda x: x["nb_articles"],
        reverse=True
    )[:limit]

    # Simplifier les spécialités
    for r in top:
        r["specialite_principale"] = max(
            r["specialites"],
            key=r["specialites"].get
        ) if r["specialites"] else "Général"
        del r["specialites"]

    return top