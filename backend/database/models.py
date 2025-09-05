from sqlalchemy import Column, Integer, String, Float, DateTime, ForeignKey, Text, Boolean
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship
from datetime import datetime

Base = declarative_base()

class User(Base):
    """User model storing Telegram user information"""
    __tablename__ = "users"
    
    id = Column(Integer, primary_key=True)
    telegram_id = Column(String(50), unique=True, nullable=False, index=True)
    telegram_username = Column(String(255))
    telegram_first_name = Column(String(255))
    telegram_last_name = Column(String(255))
    
    # Relationships
    wallet = relationship("Wallet", back_populates="user", uselist=False, cascade="all, delete-orphan")
    sent_transactions = relationship("Transaction", 
                                    foreign_keys="Transaction.sender_id",
                                    back_populates="sender")
    settings = relationship("UserSettings", back_populates="user", uselist=False, cascade="all, delete-orphan")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    is_active = Column(Boolean, default=True)
    
    def __repr__(self):
        return f"<User(telegram_id={self.telegram_id}, username={self.telegram_username})>"


class Wallet(Base):
    """Wallet model storing XRP account information (Custodial Model)"""
    __tablename__ = "wallets"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    
    # XRP Account Details
    xrp_address = Column(String(255), unique=True, nullable=False, index=True)
    encrypted_secret = Column(Text, nullable=False)  # NEVER store plaintext!
    
    # Balance tracking (cached for performance)
    balance = Column(Float, default=0.0)
    last_balance_update = Column(DateTime)
    
    # Relationships
    user = relationship("User", back_populates="wallet")
    
    # Security
    encryption_version = Column(Integer, default=1)  # Track encryption scheme
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)
    
    def __repr__(self):
        return f"<Wallet(xrp_address={self.xrp_address}, balance={self.balance})>"


class Transaction(Base):
    """Transaction model storing XRP transfer history"""
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True)
    
    # Transaction parties
    sender_id = Column(Integer, ForeignKey("users.id"))
    sender_address = Column(String(255), nullable=False)
    recipient_address = Column(String(255), nullable=False)
    
    # Transaction details
    amount = Column(Float, nullable=False)
    fee = Column(Float, default=0.00001)  # Standard XRP fee
    
    # XRP Ledger details
    tx_hash = Column(String(255), unique=True, index=True)
    ledger_index = Column(Integer)
    
    # Status tracking
    status = Column(String(50), default="pending")  # pending, confirmed, failed
    error_message = Column(Text)
    
    # Relationships
    sender = relationship("User", back_populates="sent_transactions")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    confirmed_at = Column(DateTime)
    
    def __repr__(self):
        return f"<Transaction(hash={self.tx_hash}, amount={self.amount}, status={self.status})>"


class PriceHistory(Base):
    """Price history for caching XRP price data"""
    __tablename__ = "price_history"
    
    id = Column(Integer, primary_key=True)
    
    # Price data
    price_usd = Column(Float, nullable=False)
    price_btc = Column(Float)
    market_cap = Column(Float)
    volume_24h = Column(Float)
    change_24h = Column(Float)
    
    # Source tracking
    source = Column(String(50), default="coingecko")
    
    # Timestamps
    timestamp = Column(DateTime, default=datetime.utcnow, index=True)
    
    def __repr__(self):
        return f"<PriceHistory(price_usd={self.price_usd}, timestamp={self.timestamp})>"


class UserSettings(Base):
    """User preferences and settings"""
    __tablename__ = "user_settings"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True)
    
    # Notification preferences
    price_alerts = Column(Boolean, default=False)
    transaction_notifications = Column(Boolean, default=True)
    
    # Display preferences
    currency_display = Column(String(10), default="USD")
    language = Column(String(10), default="en")
    
    # Security
    two_factor_enabled = Column(Boolean, default=False)
    pin_code = Column(String(255))  # Hashed PIN
    
    # Relationships
    user = relationship("User", back_populates="settings")
    
    # Timestamps
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)