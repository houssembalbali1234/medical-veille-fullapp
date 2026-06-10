"""
test_articles.py — Tests des articles PostgreSQL
=================================================
Teste les endpoints : /articles-pg/
"""

import pytest


# ============================================================
# LISTE DES ARTICLES
# ============================================================

@pytest.mark.asyncio
async def test_get_articles_empty(client):
    """Liste vide au départ → 200 avec liste vide."""
    response = await client.get("/articles-pg/")
    assert response.status_code == 200
    assert isinstance(response.json(), list)


@pytest.mark.asyncio
async def test_create_article_success(client, auth_headers):
    """Créer un article manuellement → 201."""
    response = await client.post("/articles-pg/", json={
        "titre": "Test Article Cancer",
        "auteurs": "Smith J, Dupont M",
        "resume": "Un article de test sur le cancer.",
        "specialite": "Oncologie",
        "source": "pubmed",
        "annee": "2024"
    }, headers=auth_headers)

    assert response.status_code == 201
    data = response.json()
    assert data["titre"] == "Test Article Cancer"
    assert data["specialite"] == "Oncologie"
    assert "id" in data


@pytest.mark.asyncio
async def test_create_article_unauthorized(client):
    """Sans token → 401."""
    response = await client.post("/articles-pg/", json={
        "titre": "Article sans auth"
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_article_by_id(client, auth_headers):
    """Récupérer un article par son ID → 200."""
    # Créer d'abord un article
    create_response = await client.post("/articles-pg/", json={
        "titre": "Article pour test ID",
        "specialite": "Cardiologie",
        "annee": "2024"
    }, headers=auth_headers)

    article_id = create_response.json()["id"]

    # Récupérer par ID
    response = await client.get(f"/articles-pg/{article_id}")
    assert response.status_code == 200
    assert response.json()["id"] == article_id


@pytest.mark.asyncio
async def test_get_article_not_found(client):
    """ID inexistant → 404."""
    fake_id = "00000000-0000-0000-0000-000000000000"
    response = await client.get(f"/articles-pg/{fake_id}")
    assert response.status_code == 404


# ============================================================
# RECHERCHE
# ============================================================

@pytest.mark.asyncio
async def test_search_articles(client, auth_headers):
    """Recherche par mot-clé → résultats filtrés."""
    # Créer un article avec un mot-clé spécifique
    await client.post("/articles-pg/", json={
        "titre": "Unique keyword XYZ123 article",
        "specialite": "Neurologie"
    }, headers=auth_headers)

    # Rechercher par ce mot-clé
    response = await client.get("/articles-pg/search?keyword=XYZ123")
    assert response.status_code == 200
    results = response.json()
    assert len(results) >= 1
    assert any("XYZ123" in a["titre"] for a in results)


@pytest.mark.asyncio
async def test_search_articles_no_results(client):
    """Recherche sans résultats → liste vide."""
    response = await client.get("/articles-pg/search?keyword=MOTCLEINTROUVABLE99999")
    assert response.status_code == 200
    assert response.json() == []