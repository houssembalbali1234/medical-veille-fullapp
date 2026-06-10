from sqlalchemy import Column, String, Boolean, DateTime, Text, Integer, Float, ForeignKey
from sqlalchemy.dialects.postgresql import UUID
from sqlalchemy.sql import func
import uuid
from app.database.database import Base

class User(Base):
    __tablename__ = "users"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    email = Column(String(255), unique=True, nullable=False)
    username = Column(String(100), unique=True, nullable=False)
    hashed_password = Column(String(255), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Article(Base):
    __tablename__ = "articles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    titre = Column(String(500), nullable=False)
    auteurs = Column(String(500), nullable=True)
    resume = Column(Text, nullable=True)
    specialite = Column(String(100), nullable=True)
    source = Column(String(100), nullable=True)
    pubmed_id = Column(String(50), nullable=True)
    annee = Column(String(10), nullable=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# 📊 INTERACTIONS UTILISATEUR (Partie 3)
# ============================================================

class UserInteraction(Base):
    __tablename__ = "user_interactions"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    pubmed_id = Column(String(100), nullable=False)
    interaction_type = Column(String(50), nullable=False)
    specialite = Column(String(100), nullable=True)
    score = Column(Float, default=1.0)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class UserPreference(Base):
    __tablename__ = "user_preferences"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    specialite = Column(String(100), nullable=False)
    score = Column(Float, default=0.0)
    nb_interactions = Column(Integer, default=0)
    updated_at = Column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class SavedArticle(Base):
    __tablename__ = "saved_articles"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    pubmed_id = Column(String(100), nullable=False)
    titre = Column(String(500), nullable=True)
    specialite = Column(String(100), nullable=True)
    note = Column(Text, nullable=True)
    saved_at = Column(DateTime(timezone=True), server_default=func.now())


# ============================================================
# 🔔 ALERTES & VEILLE (Partie 5)
# ============================================================

class KeywordAlert(Base):
    """
    Alerte sur un mot-clé.
    Ex: "immunotherapy" → notification dès qu'un article sort
    """
    __tablename__ = "keyword_alerts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    keyword = Column(String(200), nullable=False)
    specialite = Column(String(100), nullable=True)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class AuthorAlert(Base):
    """
    Suivi d'un auteur (KOL - Key Opinion Leader).
    Ex: suivre Dr. Levey → notification dès qu'il publie
    """
    __tablename__ = "author_alerts"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    author_name = Column(String(200), nullable=False)
    is_active = Column(Boolean, default=True)
    created_at = Column(DateTime(timezone=True), server_default=func.now())


class Notification(Base):
    """
    Notifications générées par le système.
    """
    __tablename__ = "notifications"
    id = Column(UUID(as_uuid=True), primary_key=True, default=uuid.uuid4)
    user_id = Column(UUID(as_uuid=True), ForeignKey("users.id"), nullable=False)
    type = Column(String(50), nullable=False)  # keyword, author, digest
    titre = Column(String(500), nullable=False)
    message = Column(Text, nullable=True)
    pubmed_id = Column(String(100), nullable=True)
    is_read = Column(Boolean, default=False)
    created_at = Column(DateTime(timezone=True), server_default=func.now())