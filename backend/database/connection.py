"""Database connection with proper typing."""

from __future__ import annotations

import logging
from collections.abc import Generator
from pathlib import Path
from typing import TYPE_CHECKING

from sqlalchemy import create_engine
from sqlalchemy.orm import Session, sessionmaker
from sqlalchemy.pool import StaticPool

from alembic import command
from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from .models import Base

if TYPE_CHECKING:
    from sqlalchemy.engine import Engine

logger = logging.getLogger(__name__)

# Global variables that will be initialized later
engine: Engine | None = None
SessionLocal: sessionmaker[Session] | None = None


def create_db_engine(database_url: str, debug: bool = False) -> Engine:
    """Create and configure database engine."""
    if database_url.startswith("sqlite"):
        # SQLite specific settings for concurrent access
        engine = create_engine(
            database_url,
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
            echo=debug,
        )
    else:
        # PostgreSQL/MySQL settings
        engine = create_engine(
            database_url,
            pool_size=20,
            max_overflow=40,
            pool_pre_ping=True,
            echo=debug,
        )
    return engine


def initialize_database_engine(database_url: str, debug: bool = False) -> None:
    """Initialize database engine and session factory."""
    global engine, SessionLocal

    if engine is not None:
        logger.warning("Database engine already initialized")
        return

    logger.info(f"Initializing database engine with URL: {database_url[:30]}...")

    # Create engine
    engine = create_db_engine(database_url, debug)

    # Create session factory
    SessionLocal = sessionmaker(
        autocommit=False,
        autoflush=False,
        bind=engine,
        class_=Session,  # Explicitly specify Session class
        expire_on_commit=False,  # Don't expire objects after commit
    )


def get_alembic_config(database_url: str) -> Config:
    """Get Alembic configuration."""
    # Get the project root directory (where alembic.ini is located)
    project_root = Path(__file__).parent.parent.parent
    alembic_cfg_path = project_root / "alembic.ini"

    if not alembic_cfg_path.exists():
        raise FileNotFoundError(f"Alembic configuration file not found at {alembic_cfg_path}")

    # Create Alembic config
    alembic_cfg = Config(str(alembic_cfg_path))

    # Set the database URL
    alembic_cfg.set_main_option("sqlalchemy.url", database_url)

    return alembic_cfg


def init_database(database_url: str | None = None, debug: bool = False) -> None:
    """Initialize database using Alembic migrations."""
    global engine

    # Initialize engine if not already done
    if engine is None:
        if database_url is None:
            raise ValueError("Database URL must be provided when engine is not initialized")
        initialize_database_engine(database_url, debug)

    if engine is None:
        raise RuntimeError("Failed to initialize database engine")

    try:
        # Check if database needs migrations
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()

        # Get Alembic configuration
        alembic_cfg = get_alembic_config(engine.url.render_as_string(hide_password=False))
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
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call initialize_database_engine first.")

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
    if SessionLocal is None:
        raise RuntimeError("Database not initialized. Call initialize_database_engine first.")

    return SessionLocal()


def check_database_health() -> bool:
    """Check if database is healthy."""
    if SessionLocal is None:
        logger.error("Database not initialized")
        return False

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


def close_database_connections() -> None:
    """Close all database connections gracefully."""
    global engine

    if engine is not None:
        logger.info("Closing database connections...")
        engine.dispose()
        logger.info("Database connections closed")
