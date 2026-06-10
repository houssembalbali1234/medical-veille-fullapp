"""
test_health.py — Tests des endpoints de base
=============================================
"""

import pytest


@pytest.mark.asyncio
async def test_root(client):
    """Page d'accueil → 200."""
    response = await client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert data["version"] == "1.0.0"
    assert "docs" in data


@pytest.mark.asyncio
async def test_health(client):
    """Health check → 200."""
    response = await client.get("/health")
    assert response.status_code == 200
    data = response.json()
    assert "status" in data
    assert "version" in data
    assert "services" in data


@pytest.mark.asyncio
async def test_docs_available(client):
    """Swagger UI disponible → 200."""
    response = await client.get("/docs")
    assert response.status_code == 200


@pytest.mark.asyncio
async def test_openapi_schema(client):
    """Schema OpenAPI disponible → 200."""
    response = await client.get("/openapi.json")
    assert response.status_code == 200
    data = response.json()
    assert data["info"]["title"] == "Medical Veille API"
    assert data["info"]["version"] == "1.0.0"