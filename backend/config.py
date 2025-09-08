"""Configuration management"""
from __future__ import annotations
import os
from pydantic_settings import BaseSettings, SettingsConfigDict
from pydantic import Field, field_validator
from typing import Optional
from cryptography.fernet import Fernet


class Settings(BaseSettings):
    """Application configuration using Pydantic with proper defaults."""
    
    model_config = SettingsConfigDict(
        env_file=".env",
        case_sensitive=False,  # This allows lowercase field names to match uppercase env vars
        env_prefix="",  # No prefix needed
        extra="allow"
    )
    
    # Application - field names match env var names (case insensitive)
    APP_NAME: str = Field(default="XRP Telegram Bot")
    APP_VERSION: str = Field(default="1.0.0")
    DEBUG: bool = Field(default=True)
    ENVIRONMENT: str = Field(default="development")
    
    # Database
    DATABASE_URL: str = Field(
        default="sqlite:///./xrp_bot.db",
        description="Database connection URL"
    )
    
    # Security
    ENCRYPTION_KEY: str = Field(
        default="",  # Will be validated/generated
        description="32-byte Fernet encryption key"
    )
    JWT_SECRET: str = Field(
        default="dev-jwt-secret-change-in-production",
        description="JWT signing secret"
    )
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRATION_HOURS: int = Field(default=24)
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str = Field(
        default="",  # Will be validated
        description="Telegram bot token from BotFather"
    )
    TELEGRAM_WEBHOOK_URL: Optional[str] = Field(
        default=None,
        description="Webhook URL for production"
    )
    
    # XRP Ledger
    XRP_NETWORK: str = Field(default="testnet")
    XRP_WEBSOCKET_URL: str = Field(
        default="wss://s.altnet.rippletest.net:51233"
    )
    XRP_JSON_RPC_URL: str = Field(
        default="https://s.altnet.rippletest.net:51234"
    )
    XRP_FAUCET_URL: str = Field(
        default="https://faucet.altnet.rippletest.net/accounts"
    )
    
    # API
    API_HOST: str = Field(default="0.0.0.0")
    API_PORT: int = Field(default=8000)
    API_URL: str = Field(default="http://localhost:8000")
    API_PREFIX: str = Field(default="/api/v1")
    
    # Redis (optional)
    REDIS_URL: Optional[str] = Field(default=None)
    CACHE_TTL: int = Field(default=300)  # 5 minutes
    
    # External APIs
    PRICE_API_URL: str = Field(
        default="https://api.coingecko.com/api/v3"
    )
    PRICE_API_KEY: Optional[str] = Field(default=None)
    
    @field_validator("ENCRYPTION_KEY", mode="before")
    @classmethod
    def validate_encryption_key(cls, v: str | None) -> str:
        """Validate or generate encryption key."""
        if not v:
            # Generate a new key for development
            key = Fernet.generate_key().decode()
            print(f"⚠️  Generated new ENCRYPTION_KEY: {key}")
            print("   Add this to your .env file for production!")
            return key
        return v
    
    @field_validator("TELEGRAM_BOT_TOKEN", mode="before")
    @classmethod
    def validate_telegram_token(cls, v: str | None) -> str:
        """Validate Telegram bot token."""
        if not v:
            # Check if we're in production
            env = os.getenv("ENVIRONMENT", "development")
            if env == "production":
                raise ValueError("TELEGRAM_BOT_TOKEN is required in production")
            # For development, use a placeholder
            print("⚠️  TELEGRAM_BOT_TOKEN not set - using placeholder")
            return "placeholder-token-for-development"
        return v
    
    @field_validator("DATABASE_URL", mode="after")
    @classmethod
    def validate_database_url(cls, v: str) -> str:
        """Ensure DATABASE_URL is properly formatted."""
        if v.startswith("postgres://"):
            # Render uses postgres:// but SQLAlchemy needs postgresql://
            return v.replace("postgres://", "postgresql://", 1)
        return v


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
            # Let the validators handle the defaults
            return Settings()
        raise


# Global settings instance
settings = get_settings()