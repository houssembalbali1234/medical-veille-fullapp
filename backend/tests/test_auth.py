"""
test_auth.py — Tests d'authentification
========================================
Teste les endpoints : /auth/register, /auth/login, /auth/me, /auth/logout
"""

import pytest


# ============================================================
# REGISTER
# ============================================================

@pytest.mark.asyncio
async def test_register_success(client):
    """Inscription réussie avec données valides."""
    response = await client.post("/auth/register", json={
        "username": "newuser",
        "email": "newuser@test.com",
        "password": "password123"
    })
    assert response.status_code == 201
    data = response.json()
    assert data["email"] == "newuser@test.com"
    assert data["username"] == "newuser"
    assert data["is_active"] is True
    assert "id" in data
    assert "hashed_password" not in data  # Ne jamais exposer le hash


@pytest.mark.asyncio
async def test_register_duplicate_email(client):
    """Inscription avec email déjà utilisé → 400."""
    await client.post("/auth/register", json={
        "username": "user1",
        "email": "duplicate@test.com",
        "password": "password123"
    })
    response = await client.post("/auth/register", json={
        "username": "user2",
        "email": "duplicate@test.com",
        "password": "password123"
    })
    assert response.status_code == 400
    assert "Email" in response.json()["detail"]


@pytest.mark.asyncio
async def test_register_duplicate_username(client):
    """Inscription avec username déjà utilisé → 400."""
    await client.post("/auth/register", json={
        "username": "sameuser",
        "email": "email1@test.com",
        "password": "password123"
    })
    response = await client.post("/auth/register", json={
        "username": "sameuser",
        "email": "email2@test.com",
        "password": "password123"
    })
    assert response.status_code == 400


@pytest.mark.asyncio
async def test_register_invalid_email(client):
    """Email invalide → 422."""
    response = await client.post("/auth/register", json={
        "username": "user",
        "email": "not-an-email",
        "password": "password123"
    })
    assert response.status_code == 422


# ============================================================
# LOGIN
# ============================================================

@pytest.mark.asyncio
async def test_login_success(client):
    """Login réussi → token JWT retourné."""
    await client.post("/auth/register", json={
        "username": "loginuser",
        "email": "login@test.com",
        "password": "password123"
    })
    response = await client.post("/auth/login", json={
        "email": "login@test.com",
        "password": "password123"
    })
    assert response.status_code == 200
    data = response.json()
    assert "access_token" in data
    assert data["token_type"] == "bearer"
    assert len(data["access_token"]) > 10


@pytest.mark.asyncio
async def test_login_wrong_password(client):
    """Mauvais mot de passe → 401."""
    await client.post("/auth/register", json={
        "username": "wrongpassuser",
        "email": "wrongpass@test.com",
        "password": "correctpassword"
    })
    response = await client.post("/auth/login", json={
        "email": "wrongpass@test.com",
        "password": "wrongpassword"
    })
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_login_unknown_email(client):
    """Email inconnu → 401."""
    response = await client.post("/auth/login", json={
        "email": "unknown@test.com",
        "password": "password123"
    })
    assert response.status_code == 401


# ============================================================
# ME
# ============================================================

@pytest.mark.asyncio
async def test_get_me_success(client, auth_headers):
    """Profil utilisateur connecté → 200."""
    response = await client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 200
    data = response.json()
    assert "id" in data
    assert "email" in data
    assert "username" in data


@pytest.mark.asyncio
async def test_get_me_without_token(client):
    """Sans token → 401."""
    response = await client.get("/auth/me")
    assert response.status_code == 401


@pytest.mark.asyncio
async def test_get_me_invalid_token(client):
    """Token invalide → 401."""
    response = await client.get(
        "/auth/me",
        headers={"Authorization": "Bearer invalid.token.here"}
    )
    assert response.status_code == 401


# ============================================================
# LOGOUT
# ============================================================

@pytest.mark.asyncio
async def test_logout_success(client, auth_headers):
    """Logout réussi → token blacklisté."""
    response = await client.post("/auth/logout", headers=auth_headers)
    assert response.status_code == 200

    # Après logout, le token ne doit plus fonctionner
    response = await client.get("/auth/me", headers=auth_headers)
    assert response.status_code == 401