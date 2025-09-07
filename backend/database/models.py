"""Database models with proper typing for Python 3.10+."""
from __future__ import annotations
from datetime import datetime, timezone

from sqlalchemy import Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column, relationship


class Base(DeclarativeBase):
    """Base class for all models."""
    pass


class User(Base):
    """User model storing Telegram user information."""
    __tablename__ = "users"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    telegram_id: Mapped[str] = mapped_column(String(50), unique=True, nullable=False, index=True)
    telegram_username: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_first_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    telegram_last_name: Mapped[str | None] = mapped_column(String(255), nullable=True)
    
    # Relationships
    wallet: Mapped[Wallet | None] = relationship(
        "Wallet", 
        back_populates="user", 
        uselist=False,
        lazy="joined"  # Eager load wallet with user
    )
    sent_transactions: Mapped[list[Transaction]] = relationship(
        "Transaction",
        foreign_keys="Transaction.sender_id",
        back_populates="sender"
    )
    settings: Mapped[UserSettings | None] = relationship(
        "UserSettings",
        back_populates="user",
        uselist=False
    )
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )
    is_active: Mapped[bool] = mapped_column(Boolean, default=True)
    
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
    encrypted_secret: Mapped[str] = mapped_column(Text, nullable=False)  # NEVER store plaintext!
    
    # Balance tracking (cached for performance)
    balance: Mapped[float] = mapped_column(Float, default=0.0)
    last_balance_update: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    # Relationships
    user: Mapped[User] = relationship("User", back_populates="wallet")
    
    # Security
    encryption_version: Mapped[int] = mapped_column(Integer, default=1)  # Track encryption scheme
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    def __repr__(self) -> str:
        return f"<Wallet(xrp_address={self.xrp_address}, balance={self.balance})>"


class Transaction(Base):
    """Transaction model storing XRP transfer history."""
    __tablename__ = "transactions"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Transaction parties
    sender_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("users.id"), nullable=True)
    sender_address: Mapped[str] = mapped_column(String(255), nullable=False)
    recipient_address: Mapped[str] = mapped_column(String(255), nullable=False)
    
    # Transaction details
    amount: Mapped[float] = mapped_column(Float, nullable=False)
    fee: Mapped[float] = mapped_column(Float, default=0.00001)  # Standard XRP fee
    
    # XRP Ledger details
    tx_hash: Mapped[str | None] = mapped_column(String(255), unique=True, index=True, nullable=True)
    ledger_index: Mapped[int | None] = mapped_column(Integer, nullable=True)
    
    # Status tracking
    status: Mapped[str] = mapped_column(String(50), default="pending")  # pending, confirmed, failed
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    
    # Relationships
    sender: Mapped[User | None] = relationship("User", back_populates="sent_transactions")
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    confirmed_at: Mapped[datetime | None] = mapped_column(DateTime, nullable=True)
    
    def __repr__(self) -> str:
        return f"<Transaction(hash={self.tx_hash}, amount={self.amount}, status={self.status})>"


class PriceHistory(Base):
    """Price history for caching XRP price data."""
    __tablename__ = "price_history"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    
    # Price data
    price_usd: Mapped[float] = mapped_column(Float, nullable=False)
    price_btc: Mapped[float | None] = mapped_column(Float, nullable=True)
    market_cap: Mapped[float | None] = mapped_column(Float, nullable=True)
    volume_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    change_24h: Mapped[float | None] = mapped_column(Float, nullable=True)
    
    # Source tracking
    source: Mapped[str] = mapped_column(String(50), default="coingecko")
    
    # Timestamps
    timestamp: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc), index=True)
    
    def __repr__(self) -> str:
        return f"<PriceHistory(price_usd={self.price_usd}, timestamp={self.timestamp})>"


class UserSettings(Base):
    """User preferences and settings."""
    __tablename__ = "user_settings"
    
    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, ForeignKey("users.id"), unique=True)
    
    # Notification preferences
    price_alerts: Mapped[bool] = mapped_column(Boolean, default=False)
    transaction_notifications: Mapped[bool] = mapped_column(Boolean, default=True)
    
    # Display preferences
    currency_display: Mapped[str] = mapped_column(String(10), default="USD")
    language: Mapped[str] = mapped_column(String(10), default="en")
    
    # Security
    two_factor_enabled: Mapped[bool] = mapped_column(Boolean, default=False)
    pin_code: Mapped[str | None] = mapped_column(String(255), nullable=True)  # Hashed PIN
    
    # Relationships
    user: Mapped[User] = relationship("User", back_populates="settings")
    
    # Timestamps
    created_at: Mapped[datetime] = mapped_column(DateTime, default=lambda: datetime.now(timezone.utc))
    updated_at: Mapped[datetime] = mapped_column(
        DateTime, 
        default=lambda: datetime.now(timezone.utc), 
        onupdate=lambda: datetime.now(timezone.utc)
    )
    
    def __repr__(self) -> str:
        return f"<UserSettings(user_id={self.user_id}, language={self.language})>"