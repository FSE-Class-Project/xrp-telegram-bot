#!/usr/bin/env python3
"""Database migration management script."""

import sys
import argparse
import logging
from pathlib import Path

from alembic.config import Config
from alembic import command
from alembic.script import ScriptDirectory
from alembic.runtime.migration import MigrationContext

# Add the project root to the path
sys.path.insert(0, str(Path(__file__).parent))

from backend.database.connection import engine, get_alembic_config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)


def create_migration(message: str) -> None:
    """Create a new migration."""
    try:
        alembic_cfg = get_alembic_config()
        command.revision(alembic_cfg, message=message, autogenerate=True)
        logger.info(f"Created migration: {message}")
    except Exception as e:
        logger.error(f"Failed to create migration: {e}")
        sys.exit(1)


def upgrade_database(revision: str = "head") -> None:
    """Upgrade database to specified revision."""
    try:
        alembic_cfg = get_alembic_config()
        command.upgrade(alembic_cfg, revision)
        logger.info(f"Database upgraded to {revision}")
    except Exception as e:
        logger.error(f"Failed to upgrade database: {e}")
        sys.exit(1)


def downgrade_database(revision: str) -> None:
    """Downgrade database to specified revision."""
    try:
        alembic_cfg = get_alembic_config()
        command.downgrade(alembic_cfg, revision)
        logger.info(f"Database downgraded to {revision}")
    except Exception as e:
        logger.error(f"Failed to downgrade database: {e}")
        sys.exit(1)


def show_current_revision() -> None:
    """Show current database revision."""
    try:
        with engine.connect() as connection:
            context = MigrationContext.configure(connection)
            current_rev = context.get_current_revision()
            
        alembic_cfg = get_alembic_config()
        script = ScriptDirectory.from_config(alembic_cfg)
        head_rev = script.get_current_head()
        
        logger.info(f"Current revision: {current_rev or 'None'}")
        logger.info(f"Head revision: {head_rev}")
        
        if current_rev != head_rev:
            logger.warning("Database is not up to date!")
        else:
            logger.info("Database is up to date!")
            
    except Exception as e:
        logger.error(f"Failed to check revision: {e}")
        sys.exit(1)


def show_history() -> None:
    """Show migration history."""
    try:
        alembic_cfg = get_alembic_config()
        command.history(alembic_cfg, verbose=True)
    except Exception as e:
        logger.error(f"Failed to show history: {e}")
        sys.exit(1)


def stamp_database(revision: str) -> None:
    """Stamp database with specified revision without running migrations."""
    try:
        alembic_cfg = get_alembic_config()
        command.stamp(alembic_cfg, revision)
        logger.info(f"Database stamped with revision {revision}")
    except Exception as e:
        logger.error(f"Failed to stamp database: {e}")
        sys.exit(1)


def main():
    """Main CLI function."""
    parser = argparse.ArgumentParser(description="Database migration management")
    subparsers = parser.add_subparsers(dest="command", help="Available commands")

    # Create migration
    create_parser = subparsers.add_parser("create", help="Create a new migration")
    create_parser.add_argument("message", help="Migration message")

    # Upgrade
    upgrade_parser = subparsers.add_parser("upgrade", help="Upgrade database")
    upgrade_parser.add_argument("revision", nargs="?", default="head", help="Target revision (default: head)")

    # Downgrade
    downgrade_parser = subparsers.add_parser("downgrade", help="Downgrade database")
    downgrade_parser.add_argument("revision", help="Target revision")

    # Current
    subparsers.add_parser("current", help="Show current revision")

    # History
    subparsers.add_parser("history", help="Show migration history")

    # Stamp
    stamp_parser = subparsers.add_parser("stamp", help="Stamp database with revision")
    stamp_parser.add_argument("revision", help="Revision to stamp")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        return

    if args.command == "create":
        create_migration(args.message)
    elif args.command == "upgrade":
        upgrade_database(args.revision)
    elif args.command == "downgrade":
        downgrade_database(args.revision)
    elif args.command == "current":
        show_current_revision()
    elif args.command == "history":
        show_history()
    elif args.command == "stamp":
        stamp_database(args.revision)


if __name__ == "__main__":
    main()