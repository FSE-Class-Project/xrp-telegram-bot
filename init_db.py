#!/usr/bin/env python
"""Database initialization script for production deployment.
Run this after deployment to initialize the database.

Usage:
    python init_db.py
"""

import logging
import os
import sys

# Add parent directory to path to import backend modules
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from backend.config import initialize_settings  # noqa: E402
from backend.database.connection import (  # noqa: E402
    init_database,
    initialize_database_engine,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


def main():
    """Initialize database for production deployment."""
    try:
        logger.info("🚀 Starting database initialization...")

        # Initialize settings
        settings = initialize_settings()
        logger.info(f"Environment: {settings.ENVIRONMENT}")
        logger.info(f"Database URL: {settings.DATABASE_URL[:30]}...")

        # Initialize database engine
        initialize_database_engine(settings.DATABASE_URL, settings.DEBUG)
        logger.info("✅ Database engine initialized")

        # Initialize database schema
        init_database()
        logger.info("✅ Database schema initialized")

        # Test database connection
        from backend.database.connection import check_database_health

        if check_database_health():
            logger.info("✅ Database health check passed")
        else:
            logger.error("❌ Database health check failed")
            sys.exit(1)

        logger.info("🎉 Database initialization completed successfully!")

    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}", exc_info=True)
        sys.exit(1)


if __name__ == "__main__":
    main()
