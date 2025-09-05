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
    created_at = Column(DateTime, default=datetime.utcnow)
    
    # TODO: Add wallet relationship

class Wallet(Base):
    """Wallet model storing XRP account information"""
    __tablename__ = "wallets"
    
    id = Column(Integer, primary_key=True)
    user_id = Column(Integer, ForeignKey("users.id"), unique=True, nullable=False)
    xrp_address = Column(String(255), unique=True, nullable=False, index=True)
    encrypted_secret = Column(Text, nullable=False)
    balance = Column(Float, default=0.0)
    created_at = Column(DateTime, default=datetime.utcnow)

class Transaction(Base):
    """Transaction model storing XRP transfer history"""
    __tablename__ = "transactions"
    
    id = Column(Integer, primary_key=True)
    sender_id = Column(Integer, ForeignKey("users.id"))
    recipient_address = Column(String(255), nullable=False)
    amount = Column(Float, nullable=False)
    tx_hash = Column(String(255), unique=True, index=True)
    created_at = Column(DateTime, default=datetime.utcnow)
