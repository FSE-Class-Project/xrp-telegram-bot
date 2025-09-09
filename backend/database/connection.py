"""Database connection with proper typing."""
from __future__ import annotations
from typing import TYPE_CHECKING
from collections.abc import Generator
import logging
import os
from pathlib import Path

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, Session
from sqlalchemy.pool import StaticPool
from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext

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


def get_alembic_config() -> Config:
    """Get Alembic configuration."""
    # Get the project root directory (where alembic.ini is located)
    project_root = Path(__file__).parent.parent.parent
    alembic_cfg_path = project_root / "alembic.ini"
    
    if not alembic_cfg_path.exists():
        raise FileNotFoundError(f"Alembic configuration file not found at {alembic_cfg_path}")
    
    # Create Alembic config
    alembic_cfg = Config(str(alembic_cfg_path))
    
    # Set the database URL from our settings
    alembic_cfg.set_main_option("sqlalchemy.url", settings.DATABASE_URL)
    
    return alembic_cfg


def init_database() -> None:
    """Initialize database using Alembic migrations."""
    try:
        # Check if database needs migrations
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()
            
        # Get Alembic configuration
        alembic_cfg = get_alembic_config()
        script = ScriptDirectory.from_config(alembic_cfg)
        head_rev = script.get_current_head()
        
        if current_rev is None:
            # Database not initialized, run all migrations
            logger.info("Database not initialized. Running initial migration...")
            command.upgrade(alembic_cfg, "head")
            logger.info("Database initialized successfully with migrations!")
        elif current_rev != head_rev:
            # Database needs upgrade
            logger.info(f"Database upgrade needed: {current_rev} -> {head_rev}")
            command.upgrade(alembic_cfg, "head")
            logger.info("Database upgraded successfully!")
        else:
            # Database is up to date
            logger.info("Database is up to date!")
            
    except Exception as e:
        logger.error(f"Failed to initialize database with migrations: {str(e)}")
        # Fallback to direct table creation for development
        logger.warning("Falling back to direct table creation...")
        try:
            Base.metadata.create_all(bind=engine)
            logger.info("Database tables created successfully (fallback)!")
        except Exception as fallback_error:
            logger.error(f"Fallback table creation also failed: {str(fallback_error)}")
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