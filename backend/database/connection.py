"""Database connection with proper typing."""
from __future__ import annotations
from typing import TYPE_CHECKING
from collections.abc import Generator
import logging

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool

from .models import Base
from ..config import settings

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)


def create_db_engine() -> Engine:
    """Create and configure database engine."""
    if settings.DATABASE_URL.startswith("sqlite"):
        # SQLite specific settings for concurrent access
        engine = create_engine(
            settings.DATABASE_URL,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=settings.DEBUG
        )
    else:
        # PostgreSQL/MySQL settings
        engine = create_engine(
            settings.DATABASE_URL,
            pool_size=20,
            max_overflow=40,
            pool_pre_ping=True,
            echo=settings.DEBUG
        )
    return engine


# Create engine
engine = create_db_engine()

# Create session factory
SessionLocal = sessionmaker(
    autocommit=False, 
    autoflush=False, 
    bind=engine,
    class_=Session,  # Explicitly specify Session class
    expire_on_commit=False  # Don't expire objects after commit
)


def init_database() -> None:
    """Initialize database tables."""
    try:
        Base.metadata.create_all(bind=engine)
        logger.info("Database tables created successfully!")
    except Exception as e:
        logger.error(f"Failed to create database tables: {str(e)}")
        raise


def get_db() -> Generator[Session, None, None]:
    """
    Dependency for getting database session.
    Yields a database session and closes it after use.
    """
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


def get_db_session() -> Session:
    """
    Get a database session directly (for non-FastAPI contexts).
    Remember to close the session when done.
    """
    return SessionLocal()


def check_database_health() -> bool:
    """Check if database is healthy."""
    try:
        db = SessionLocal()
        try:
            from sqlalchemy import text
            db.execute(text("SELECT 1"))
            return True
        finally:
            db.close()
    except Exception as e:
        logger.error(f"Database health check failed: {str(e)}")
        return False