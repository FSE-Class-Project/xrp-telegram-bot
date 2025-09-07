"""Configuration management with proper typing and validation."""
from __future__ import annotations
import os
from pydantic_settings import BaseSettings
from pydantic import Field, validator
from typing import Optional


class Settings(BaseSettings):
    """Application configuration using Pydantic with proper defaults."""
    
    # Application
    APP_NAME: str = "XRP Telegram Bot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=True, env="DEBUG")
    ENVIRONMENT: str = Field(default="development", env="ENVIRONMENT")
    
    # Database
    DATABASE_URL: str = Field(
        default="sqlite:///./xrp_bot.db",
        env="DATABASE_URL"
    )
    
    # Security - with validation for required fields
    ENCRYPTION_KEY: str = Field(
        default=...,  # Required field
        env="ENCRYPTION_KEY",
        description="32-byte Fernet encryption key"
    )
    JWT_SECRET: str = Field(
        default="dev-jwt-secret-change-in-production",
        env="JWT_SECRET"
    )
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    
    # Telegram - with validation
    TELEGRAM_BOT_TOKEN: str = Field(
        default=...,  # Required field
        env="TELEGRAM_BOT_TOKEN",
        description="Telegram bot token from BotFather"
    )
    TELEGRAM_WEBHOOK_URL: Optional[str] = Field(
        default=None,
        env="TELEGRAM_WEBHOOK_URL"
    )
    
    # XRP Ledger
    XRP_NETWORK: str = Field(default="testnet", env="XRP_NETWORK")
    XRP_WEBSOCKET_URL: str = Field(
        default="wss://s.altnet.rippletest.net:51233",
        env="XRP_WEBSOCKET_URL"
    )
    XRP_JSON_RPC_URL: str = Field(
        default="https://s.altnet.rippletest.net:51234",
        env="XRP_JSON_RPC_URL"
    )
    XRP_FAUCET_URL: str = Field(
        default="https://faucet.altnet.rippletest.net/accounts",
        env="XRP_FAUCET_URL"
    )
    
    # API
    API_HOST: str = Field(default="0.0.0.0", env="API_HOST")
    API_PORT: int = Field(default=8000, env="API_PORT")
    API_URL: str = Field(
        default="http://localhost:8000",
        env="API_URL"
    )
    API_PREFIX: str = "/api/v1"
    
    # Redis (optional)
    REDIS_URL: Optional[str] = Field(default=None, env="REDIS_URL")
    CACHE_TTL: int = 300  # 5 minutes
    
    # External APIs
    PRICE_API_URL: str = Field(
        default="https://api.coingecko.com/api/v3",
        env="PRICE_API_URL"
    )
    PRICE_API_KEY: Optional[str] = Field(default=None, env="PRICE_API_KEY")
    
    @validator("ENCRYPTION_KEY", pre=True)
    def validate_encryption_key(cls, v: str | None) -> str:
        """Validate or generate encryption key."""
        if v is None or v == "":
            # Generate a new key for development
            from cryptography.fernet import Fernet
            key = Fernet.generate_key().decode()
            print(f"⚠️  Generated new ENCRYPTION_KEY: {key}")
            print("   Add this to your .env file for production!")
            return key
        return v
    
    @validator("TELEGRAM_BOT_TOKEN", pre=True)
    def validate_telegram_token(cls, v: str | None) -> str:
        """Validate Telegram bot token."""
        if v is None or v == "":
            if os.getenv("ENVIRONMENT", "development") == "production":
                raise ValueError("TELEGRAM_BOT_TOKEN is required in production")
            # For development, use a placeholder
            print("⚠️  TELEGRAM_BOT_TOKEN not set - using placeholder")
            return "placeholder-token-for-development"
        return v
    
    @validator("DATABASE_URL")
    def validate_database_url(cls, v: str) -> str:
        """Ensure DATABASE_URL is properly formatted."""
        if v.startswith("postgres://"):
            # Render uses postgres:// but SQLAlchemy needs postgresql://
            return v.replace("postgres://", "postgresql://", 1)
        return v
    
    class Config:
        env_file = ".env"
        case_sensitive = True
        # Allow extra fields from environment
        extra = "allow"


# Create settings instance with error handling
def get_settings() -> Settings:
    """Get settings with proper error handling."""
    try:
        return Settings()
    except Exception as e:
        print(f"❌ Configuration error: {e}")
        print("   Please check your .env file")
        # Return settings with defaults for development
        if os.getenv("ENVIRONMENT", "development") == "development":
            print("   Using development defaults...")
            return Settings(
                ENCRYPTION_KEY=os.getenv("ENCRYPTION_KEY", ""),
                TELEGRAM_BOT_TOKEN=os.getenv("TELEGRAM_BOT_TOKEN", "")
            )
        raise


# Global settings instance
settings = get_settings()