from fastapi import APIRouter, Depends, HTTPException
from fastapi.security import OAuth2PasswordBearer
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from passlib.context import CryptContext
from jose import jwt
from dotenv import load_dotenv

from app.database.database import get_db
from app.models import User
from app.shemas.schemas import (
    UserCreate,
    UserResponse,
    LoginRequest,
    TokenResponse
)
from app.database import redis_database
from app.database.redis_database import (
    blacklist_token,
    is_token_blacklisted,
    session_create,
    session_delete,
    session_get
)

import os

# ============================================================
# LOAD .ENV
# ============================================================

load_dotenv()

SECRET = os.getenv("SECRET_KEY")

if not SECRET:
    raise RuntimeError(
        "SECRET_KEY manquante dans les variables d'environnement !"
    )

# ============================================================
# ROUTER + SECURITY
# ============================================================

router = APIRouter(
    prefix="/auth",
    tags=["Auth"]
)

pwd = CryptContext(
    schemes=["bcrypt"],
    deprecated="auto"
)

oauth2_scheme = OAuth2PasswordBearer(
    tokenUrl="/auth/login"
)

# ============================================================
# GET CURRENT USER
# ============================================================

async def get_current_user(
    token: str = Depends(oauth2_scheme),
    db: AsyncSession = Depends(get_db)
):
    if await is_token_blacklisted(token):
        raise HTTPException(
            status_code=401,
            detail="Token revoqué, veuillez vous reconnecter"
        )

    try:
        payload = jwt.decode(
            token,
            SECRET,
            algorithms=["HS256"]
        )
        user_id = payload.get("sub")

        if not user_id:
            raise HTTPException(
                status_code=401,
                detail="Token invalide"
            )

    except Exception:
        raise HTTPException(
            status_code=401,
            detail="Token invalide ou expiré"
        )

    result = await db.execute(
        select(User).where(User.id == user_id)
    )
    user = result.scalar_one_or_none()

    if not user:
        raise HTTPException(
            status_code=401,
            detail="Utilisateur introuvable"
        )

    return user


# ============================================================
# REGISTER
# ============================================================

@router.post(
    "/register",
    response_model=UserResponse,
    status_code=201
)
async def register(
    data: UserCreate,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.email == data.email)
    )

    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Email déjà utilisé"
        )

    result = await db.execute(
        select(User).where(User.username == data.username)
    )

    if result.scalar_one_or_none():
        raise HTTPException(
            status_code=400,
            detail="Username déjà utilisé"
        )

    user = User(
        email=data.email,
        username=data.username,
        hashed_password=pwd.hash(data.password)
    )

    try:
        db.add(user)
        await db.commit()
        await db.refresh(user)
        return user

    except IntegrityError:
        await db.rollback()
        raise HTTPException(
            status_code=400,
            detail="Email ou username déjà utilisé"
        )


# ============================================================
# LOGIN
# ============================================================

@router.post(
    "/login",
    response_model=TokenResponse
)
async def login(
    data: LoginRequest,
    db: AsyncSession = Depends(get_db)
):
    result = await db.execute(
        select(User).where(User.email == data.email)
    )

    user = result.scalar_one_or_none()

    if not user or not pwd.verify(
        data.password,
        user.hashed_password
    ):
        raise HTTPException(
            status_code=401,
            detail="Email ou mot de passe incorrect"
        )

    # ✅ CORRECTION : utiliser redis_database.redis_client
    await redis_database.redis_client.delete(
        f"session:{user.id}"
    )

    token = jwt.encode(
        {
            "sub": str(user.id)
        },
        SECRET,
        algorithm="HS256"
    )

    await session_create(
        str(user.id),
        {
            "user_id": str(user.id),
            "email": user.email,
            "username": user.username
        }
    )

    return TokenResponse(
        access_token=token
    )


# ============================================================
# LOGOUT
# ============================================================

@router.post("/logout")
async def logout(
    token: str = Depends(oauth2_scheme),
    current_user: User = Depends(get_current_user)
):
    await blacklist_token(token)

    await session_delete(
        str(current_user.id)
    )

    return {
        "message": "Déconnexion réussie !"
    }


# ============================================================
# ME
# ============================================================

@router.get("/me")
async def get_me(
    current_user: User = Depends(get_current_user)
):
    session = await session_get(
        str(current_user.id)
    )

    return {
        "id": str(current_user.id),
        "email": current_user.email,
        "username": current_user.username,
        "is_active": current_user.is_active,
        "session_active": session is not None
    }