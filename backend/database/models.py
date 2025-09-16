"""SQLAlchemy models for XRP Telegram Bot."""

from __future__ import annotations

from datetime import datetime, timezone
from typing import TYPE_CHECKING

from sqlalchemy import (
    Boolean,
    DateTime,
    Float,
    ForeignKey,
    Integer,
    String,
    Text,
    UniqueConstraint,
)
from sqlalchemy.orm import (
    declarative_base,
    relationship,
)
from sqlalchemy import Column

if TYPE_CHECKING:
    # This prevents circular imports while still providing type hints
    pass


Base = declarative_base()
# Base class for all models


class User(Base):
    """User model storing Telegram user information."""

    __tablename__ = "users"

    id = Column(Integer, primary_key=True)
    telegram_id = Column(String(50), unique=True, nullable=False, index=True)
    telegram_username = Column(String(255), nullable=True, default=None)
    telegram_first_name = Column(String(255), nullable=True, default=None)
    telegram_last_name = Column(String(255), nullable=True, default=None)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )
    is_active = Column(Boolean, default=True, nullable=False)

    # Relationships - use string references to avoid circular imports
    wallet = relationship(
        "Wallet", back_populates="user", uselist=False, lazy="selectin"
    )
    sent_transactions = relationship(
        "Transaction", foreign_keys="Transaction.sender_id", back_populates="sender", lazy="select"
    )
    beneficiaries = relationship(
        "Beneficiary",
        back_populates="user",
        cascade="all, delete-orphan",
        lazy="selectin",
    )
    settings = relationship(
        "UserSettings", back_populates="user", uselist=False, lazy="selectin"
    )

    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.telegram_username})>"


class Wallet(Base):
    """Wallet model storing XRP account information (Custodial Model)."""

    __tablename__ = "wallets"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id"), unique=True, nullable=False
    )

    # XRP Account Details
    xrp_address = Column(String(255), unique=True, nullable=False, index=True)
    encrypted_secret = Column(Text, nullable=False)

    # Balance tracking (cached for performance)
    balance = Column(Float, default=0.0, nullable=False)
    last_balance_update = Column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Security
    encryption_version = Column(Integer, default=1, nullable=False)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user = relationship("User", back_populates="wallet")

    def __repr__(self) -> str:
        return f"<Wallet(id={self.id}, xrp_address={self.xrp_address}, balance={self.balance})>"


class Transaction(Base):
    """Transaction model storing XRP transfer history."""

    __tablename__ = "transactions"

    id = Column(Integer, primary_key=True)

    # Transaction parties
    sender_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, default=None
    )
    sender_address = Column(String(255), nullable=False)
    recipient_address = Column(String(255), nullable=False)

    # Transaction details
    amount = Column(Float, nullable=False)
    fee = Column(Float, default=0.00001, nullable=False)

    # Idempotency key for preventing duplicate transactions
    idempotency_key = Column(
        String(255), unique=True, index=True, nullable=True, default=None
    )

    # XRP Ledger details
    tx_hash = Column(
        String(255), unique=True, index=True, nullable=True, default=None
    )
    ledger_index = Column(Integer, nullable=True, default=None)

    # Status tracking
    status = Column(String(50), default="pending", nullable=False)
    error_message = Column(Text, nullable=True, default=None)
    retry_count = Column(Integer, default=0, nullable=False)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    confirmed_at = Column(
        DateTime(timezone=True), nullable=True, default=None
    )

    # Relationships
    sender = relationship("User", back_populates="sent_transactions")

    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, hash={self.tx_hash}, amount={self.amount}, status={self.status})>"


class Beneficiary(Base):
    """Beneficiary aliases for quick transactions."""

    __tablename__ = "beneficiaries"
    __table_args__ = (
        UniqueConstraint("user_id", "alias", name="uq_beneficiary_user_alias"),
    )

    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), nullable=False, index=True)
    alias = Column(String(100), nullable=False)
    address = Column(String(255), nullable=False)

    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    user = relationship("User", back_populates="beneficiaries")

    def __repr__(self) -> str:
        return f"<Beneficiary(id={self.id}, alias={self.alias}, address={self.address})>"


class PriceHistory(Base):
    """Price history for caching XRP price data."""

    __tablename__ = "price_history"

    id = Column(Integer, primary_key=True)

    # Price data
    price_usd = Column(Float, nullable=False)
    price_btc = Column(Float, nullable=True, default=None)
    market_cap = Column(Float, nullable=True, default=None)
    volume_24h = Column(Float, nullable=True, default=None)
    change_24h = Column(Float, nullable=True, default=None)

    # Source tracking
    source = Column(String(50), default="coingecko", nullable=False)

    # Timestamps
    timestamp = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=False,
    )

    def __repr__(self) -> str:
        return (
            f"<PriceHistory(id={self.id}, price_usd={self.price_usd}, timestamp={self.timestamp})>"
        )


class IdempotencyRecord(Base):
    """Idempotency tracking for preventing duplicate operations."""

    __tablename__ = "idempotency_records"

    id = Column(Integer, primary_key=True)

    # Idempotency tracking
    idempotency_key = Column(
        String(255), unique=True, index=True, nullable=False
    )
    user_id = Column(
        Integer, ForeignKey("users.id"), nullable=True, default=None
    )
    operation_type = Column(String(50), nullable=False)

    # Request data for comparison
    request_hash = Column(String(64), nullable=False)  # SHA256 hash
    request_data = Column(Text, nullable=False)  # JSON string

    # Response tracking
    response_status = Column(
        String(20), nullable=False
    )  # success, error, processing
    response_data = Column(Text, nullable=True, default=None)

    # Related records
    transaction_id = Column(
        Integer, ForeignKey("transactions.id"), nullable=True, default=None
    )

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    expires_at = Column(DateTime(timezone=True), nullable=False)

    # Relationships
    user = relationship("User")
    transaction = relationship("Transaction")

    def __repr__(self) -> str:
        return f"<IdempotencyRecord(key={self.idempotency_key}, operation={self.operation_type}, status={self.response_status})>"


class UserSettings(Base):
    """User preferences and settings."""

    __tablename__ = "user_settings"

    id = Column(Integer, primary_key=True)
    user_id = Column(
        Integer, ForeignKey("users.id"), unique=True, nullable=False
    )

    # Notification preferences
    price_alerts = Column(Boolean, default=False, nullable=False)
    transaction_notifications = Column(Boolean, default=True, nullable=False)

    # Display preferences
    currency_display = Column(String(10), default="USD", nullable=False)
    language = Column(String(10), default="en", nullable=False)

    # Security
    two_factor_enabled = Column(Boolean, default=False, nullable=False)
    pin_code = Column(String(255), nullable=True, default=None)

    # Timestamps
    created_at = Column(
        DateTime(timezone=True), default=lambda: datetime.now(timezone.utc), nullable=False
    )
    updated_at = Column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False,
    )

    # Relationships
    user = relationship("User", back_populates="settings")

    def __repr__(self) -> str:
        return f"<UserSettings(id={self.id}, user_id={self.user_id}, language={self.language})>"


# Verify that all models are defined
__all__ = [
    "Base",
    "User",
    "Wallet",
    "Transaction",
    "PriceHistory",
    "IdempotencyRecord",
    "UserSettings",
]
