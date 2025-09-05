import os
from typing import Optional

try:
    from pydantic_settings import BaseSettings  # Pydantic v2
except ImportError:
    from pydantic import BaseSettings  # Pydantic v1

class Settings(BaseSettings):
    """Application configuration using Pydantic"""
    
    # Application
    APP_NAME: str = "XRP Telegram Bot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = os.getenv("DEBUG", "true").lower() == "true"
    ENVIRONMENT: str = os.getenv("ENVIRONMENT", "development")
    
    # Database - will use Render's DATABASE_URL in production
    DATABASE_URL: str = os.getenv("DATABASE_URL", "sqlite:///./xrp_bot.db")
    
    # Security - Generate these if not provided
    ENCRYPTION_KEY: str = os.getenv("ENCRYPTION_KEY", "")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "")
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_WEBHOOK_URL: Optional[str] = os.getenv("TELEGRAM_WEBHOOK_URL", None)
    
    # XRP Ledger
    XRP_NETWORK: str = "testnet"
    XRP_WEBSOCKET_URL: str = "wss://s.altnet.rippletest.net:51233"
    XRP_JSON_RPC_URL: str = "https://s.altnet.rippletest.net:51234"
    XRP_FAUCET_URL: str = "https://faucet.altnet.rippletest.net/accounts"
    
    # API Configuration
    API_HOST: str = "0.0.0.0"
    API_PORT: int = int(os.getenv("PORT", 8000))  # Render provides PORT
    
    # Render Detection
    RENDER: bool = os.getenv("RENDER", "false").lower() == "true"
    RENDER_EXTERNAL_URL: Optional[str] = os.getenv("RENDER_EXTERNAL_URL", None)
    
    @property
    def api_url(self) -> str:
        """Dynamic API URL based on environment"""
        if self.RENDER and self.RENDER_EXTERNAL_URL:
            # On Render, use the public URL
            return f"https://{self.RENDER_EXTERNAL_URL}"
        elif self.ENVIRONMENT == "production":
            # Other production environments
            return os.getenv("API_URL", "http://localhost:8000")
        else:
            # Local development
            return f"http://localhost:{self.API_PORT}"
    
    @property
    def sqlalchemy_database_url(self) -> str:
        """
        Convert DATABASE_URL to SQLAlchemy format.
        Handles Render's postgres:// to postgresql:// conversion.
        """
        url = self.DATABASE_URL
        
        # Render uses 'postgres://' but SQLAlchemy needs 'postgresql://'
        if url.startswith("postgres://"):
            url = url.replace("postgres://", "postgresql://", 1)
        
        # Add SSL mode for Render PostgreSQL
        if self.RENDER and "postgresql://" in url and "sslmode" not in url:
            separator = "&" if "?" in url else "?"
            url += f"{separator}sslmode=require"
        
        return url
    
    @property
    def is_production(self) -> bool:
        """Check if running in production"""
        return self.ENVIRONMENT == "production" or self.RENDER
    
    @property
    def is_sqlite(self) -> bool:
        """Check if using SQLite"""
        return "sqlite" in self.DATABASE_URL.lower()
    
    def generate_encryption_key(self) -> str:
        """Generate encryption key if not provided"""
        if not self.ENCRYPTION_KEY:
            from cryptography.fernet import Fernet
            key = Fernet.generate_key().decode()
            print(f"⚠️  Generated ENCRYPTION_KEY: {key}")
            print("Add this to your .env file or Render environment variables!")
            return key
        return self.ENCRYPTION_KEY
    
    def generate_jwt_secret(self) -> str:
        """Generate JWT secret if not provided"""
        if not self.JWT_SECRET:
            import secrets
            secret = secrets.token_urlsafe(32)
            print(f"⚠️  Generated JWT_SECRET: {secret}")
            print("Add this to your .env file or Render environment variables!")
            return secret
        return self.JWT_SECRET
    
    def validate_config(self) -> bool:
        """Validate required configuration"""
        errors = []
        
        if not self.TELEGRAM_BOT_TOKEN:
            errors.append("TELEGRAM_BOT_TOKEN is required")
        
        if self.is_production:
            if not self.ENCRYPTION_KEY:
                errors.append("ENCRYPTION_KEY is required in production")
            if not self.JWT_SECRET:
                errors.append("JWT_SECRET is required in production")
        
        if errors:
            print("❌ Configuration errors:")
            for error in errors:
                print(f"  - {error}")
            return False
        
        return True
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings()

# Auto-generate keys in development (not production)
if not settings.is_production:
    if not settings.ENCRYPTION_KEY:
        settings.ENCRYPTION_KEY = settings.generate_encryption_key()
    if not settings.JWT_SECRET:
        settings.JWT_SECRET = settings.generate_jwt_secret()

# Validate configuration
if not settings.validate_config():
    if settings.is_production:
        raise ValueError("Invalid configuration for production environment")