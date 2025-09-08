"""SQLAlchemy models"""
from __future__ import annotations
from typing import TYPE_CHECKING, Optional, List
from decimal import Decimal
from datetime import datetime, timezone

from sqlalchemy import String, Integer, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import (
    DeclarativeBase,
    Mapped,
    mapped_column,
    relationship,
    MappedAsDataclass
)

if TYPE_CHECKING:
    # Avoid circular imports
    pass


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class User(Base):
    """User model storing Telegram user information."""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    telegram_username: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    telegram_first_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    telegram_last_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Relationships
    wallet: Mapped[Optional["Wallet"]] = relationship(
        "Wallet",
        back_populates="user",
        uselist=False,
        lazy="selectin"  # Eager load wallet
    )
    sent_transactions: Mapped[List["Transaction"]] = relationship(
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
        return f"<User(telegram_id={self.telegram_id}, username={self.telegram_username})>"


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
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    last_balance_update: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Security
    encryption_version: Mapped[int] = mapped_column(Integer, default=1)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="wallet")
    
    def __repr__(self) -> str:
        return f"<Wallet(xrp_address={self.xrp_address}, balance={self.balance})>"


class Transaction(Base):
    """Transaction model storing XRP transfer history."""
    __tablename__ = "transactions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Transaction parties
    sender_id: Mapped[Optional[int]] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        nullable=True
    )
    sender_address: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_address: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Transaction details
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    fee: Mapped[float] = mapped_column(Float, default=0.00001)
    
    # XRP Ledger details
    tx_hash: Mapped[Optional[str]] = mapped_column(String(255), unique=True, index=True, nullable=True)
    ledger_index: Mapped[Optional[int]] = mapped_column(Integer, nullable=True)
    
    # Status tracking
    status: Mapped[str] = mapped_column(String(50), default="pending")
    error_message: Mapped[Optional[str]] = mapped_column(Text, nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    confirmed_at: Mapped[Optional[datetime]] = mapped_column(
        DateTime(timezone=True),
        nullable=True
    )
    
    # Relationships
    sender: Mapped[Optional["User"]] = relationship(
        "User",
        back_populates="sent_transactions"
    )
    
    def __repr__(self) -> str:
        return f"<Transaction(hash={self.tx_hash}, amount={self.amount}, status={self.status})>"


class PriceHistory(Base):
    """Price history for caching XRP price data."""
    __tablename__ = "price_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Price data
    price_usd: Mapped[float] = mapped_column(Float, nullable=False)
    price_btc: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    market_cap: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    volume_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    change_24h: Mapped[Optional[float]] = mapped_column(Float, nullable=True)
    
    # Source tracking
    source: Mapped[str] = mapped_column(String(50), default="coingecko")
    
    # Timestamps
    timestamp: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        index=True
    )
    
    def __repr__(self) -> str:
        return f"<PriceHistory(price_usd={self.price_usd}, timestamp={self.timestamp})>"


class UserSettings(Base):
    """User preferences and settings."""
    __tablename__ = "user_settings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(
        Integer,
        ForeignKey("users.id"),
        unique=True
    )
    
    # Notification preferences
    price_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
    transaction_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Display preferences
    currency_display: Mapped[str] = mapped_column(String(10), default="USD")
    language: Mapped[str] = mapped_column(String(10), default="en")
    
    # Security
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    pin_code: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc)
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        default=lambda: datetime.now(timezone.utc),
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    # Relationships
    user: Mapped["User"] = relationship("User", back_populates="settings")
    
    def __repr__(self) -> str:
        return f"<UserSettings(user_id={self.user_id}, language={self.language})>"