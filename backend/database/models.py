"""SQLAlchemy models for XRP Telegram Bot."""
from __future__ import annotations

from typing import TYPE_CHECKING, Optional
from datetime import datetime, timezone

from sqlalchemy import (
    String, 
    Integer, 
    Float, 
    DateTime, 
    ForeignKey, 
    Text, 
    Boolean,
)
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
)

if TYPE_CHECKING:
    # This prevents circular imports while still providing type hints
    pass


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class User(Base):
    """User model storing Telegram user information."""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)
    telegram_first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)
    telegram_last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Relationships - use string references to avoid circular imports
    wallet: Mapped[Optional["Wallet"]] = relationship(
        "Wallet",
        back_populates="user",
        uselist=False,
        lazy="selectin"
    )
    sent_transactions: Mapped[list["Transaction"]] = relationship(
        "Transaction",
        foreign_keys="Transaction.sender_id",
        back_populates="sender",
        lazy="select"
    )
    settings: Mapped[Optional["UserSettings"]] = relationship(
        "UserSettings",
        back_populates="user",
        uselist=False,
        lazy="selectin"
    )
    
    def __repr__(self) -> str:
        return f"<User(id={self.id}, telegram_id={self.telegram_id}, username={self.telegram_username})>"


class Wallet(Base):
    """Wallet model storing XRP account information (Custodial Model)."""
    __tablename__ = "wallets"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        unique=True,
        nullable=False
    )
    
    # XRP Account Details
    xrp_address: Mapped[str] = mapped_column(String(255), unique=True, nullable=False, index=True)
    encrypted_secret: Mapped[str] = mapped_column(Text, nullable=False)
    
    # Balance tracking (cached for performance)
    balance: Mapped[float] = mapped_column(Float, default=0.0, nullable=False)
    last_balance_update: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None
    )
    
    # Security
    encryption_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="wallet")
    
    def __repr__(self) -> str:
        return f"<Wallet(id={self.id}, xrp_address={self.xrp_address}, balance={self.balance})>"


class Transaction(Base):
    """Transaction model storing XRP transfer history."""
    __tablename__ = "transactions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Transaction parties
    sender_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True,
        default=None
    )
    sender_address: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_address: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Transaction details
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    fee: Mapped[float] = mapped_column(Float, default=0.00001, nullable=False)
    
    # XRP Ledger details
    tx_hash: Mapped[Optional[str]] = mapped_column(
        String(255), 
        unique=True, 
        index=True, 
        nullable=True,
        default=None
    )
    ledger_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True, default=None)
    
    # Status tracking
    status: Mapped[str] = mapped_column(String(50), default="pending", nullable=False)
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True, default=None)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
        default=None
    )
    
    # Relationships
    sender: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="sent_transactions"
    )
    
    def __repr__(self) -> str:
        return f"<Transaction(id={self.id}, hash={self.tx_hash}, amount={self.amount}, status={self.status})>"


class PriceHistory(Base):
    """Price history for caching XRP price data."""
    __tablename__ = "price_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Price data
    price_usd: Mapped[float] = mapped_column(Float, nullable=False)
    price_btc: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    market_cap: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    volume_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    change_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True, default=None)
    
    # Source tracking
    source: Mapped[str] = mapped_column(String(50), default="coingecko", nullable=False)
    
    # Timestamps
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True,
        nullable=False
    )
    
    def __repr__(self) -> str:
        return f"<PriceHistory(id={self.id}, price_usd={self.price_usd}, timestamp={self.timestamp})>"


class UserSettings(Base):
    """User preferences and settings."""
    __tablename__ = "user_settings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        unique=True,
        nullable=False
    )
    
    # Notification preferences
    price_alerts: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    transaction_notifications: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    
    # Display preferences
    currency_display: Mapped[str] = mapped_column(String(10), default="USD", nullable=False)
    language: Mapped[str] = mapped_column(String(10), default="en", nullable=False)
    
    # Security
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    pin_code: Mapped[Optional[str]] = mapped_column(String(255), nullable=True, default=None)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc),
        nullable=False
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="settings")
    
    def __repr__(self) -> str:
        return f"<UserSettings(id={self.id}, user_id={self.user_id}, language={self.language})>"


# Verify that all models are defined
__all__ = [
    "Base",
    "User",
    "Wallet",
    "Transaction",
    "PriceHistory",
    "UserSettings",
]