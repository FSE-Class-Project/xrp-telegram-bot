"""Database module initialization."""
from __future__ import annotations

# Import models
from .models import (
    Base,
    User,
    Wallet,
    Transaction,
    PriceHistory,
    UserSettings,
)

# Import connection utilities
from .connection import (
    engine,
    SessionLocal,
    init_database,
    get_db,
)

__all__ = [
    # Models
    "Base",
    "User",
    "Wallet",
    "Transaction",
    "PriceHistory",
    "UserSettings",
    # Connection utilities
    "engine",
    "SessionLocal",
    "init_database",
    "get_db",
]