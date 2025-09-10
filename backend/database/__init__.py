"""Database module initialization."""

from __future__ import annotations

# Import connection utilities
from .connection import (
    SessionLocal,
    engine,
    get_db,
    init_database,
)

# Import models
from .models import (
    Base,
    PriceHistory,
    Transaction,
    User,
    UserSettings,
    Wallet,
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
