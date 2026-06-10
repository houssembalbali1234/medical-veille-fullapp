from pydantic import BaseModel, EmailStr
from typing import Optional
from uuid import UUID
from datetime import datetime

class UserCreate(BaseModel):
    email: EmailStr
    username: str
    password: str

class UserResponse(BaseModel):
    id: UUID
    email: str
    username: str
    is_active: bool
    class Config:
        from_attributes = True

class LoginRequest(BaseModel):
    email: EmailStr
    password: str

class TokenResponse(BaseModel):
    access_token: str
    token_type: str = "bearer"

class ArticleCreate(BaseModel):
    titre: str
    auteurs: Optional[str] = None
    resume: Optional[str] = None
    specialite: Optional[str] = None
    source: Optional[str] = None
    annee: Optional[str] = None

class ArticleResponse(BaseModel):
    id: UUID
    titre: str
    auteurs: Optional[str]
    resume: Optional[str]
    specialite: Optional[str]
    source: Optional[str]
    annee: Optional[str]
    created_at: datetime
    class Config:
        from_attributes = True