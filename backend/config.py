import os
from pydantic_settings import BaseSettings
from typing import Optional

class Settings(BaseSettings):
    """Application configuration using Pydantic"""
    
    # Application
    APP_NAME: str = "XRP Telegram Bot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"
    
    # Database - Auto-detect based on environment
    DATABASE_URL: str = ""
    
    # Security
    ENCRYPTION_KEY: str = ""
    JWT_SECRET: str = "dev-jwt-secret-change-in-production"
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    BOT_API_KEY: str = "dev-bot-api-key-change-in-production"
    ADMIN_API_KEY: str = "dev-admin-api-key-change-in-production"
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_WEBHOOK_URL: Optional[str] = None
    TELEGRAM_WEBHOOK_SECRET: str = "dev-webhook-secret-change-in-production"
    
    # XRP Ledger
    XRP_NETWORK: str = "testnet"
    XRP_WEBSOCKET_URL: str = "wss://s.altnet.rippletest.net:51233"
    XRP_JSON_RPC_URL: str = "https://s.altnet.rippletest.net:51234"
    XRP_FAUCET_URL: str = "https://faucet.altnet.rippletest.net/accounts"
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_URL: str = "http://localhost:8000"
    API_PREFIX: str = "/api/v1"
    
    # Redis (optional)
    REDIS_URL: Optional[str] = None
    CACHE_TTL: int = 300  # 5 minutes
    
    # External APIs
    PRICE_API_URL: str = "https://api.coingecko.com/api/v3"
    PRICE_API_KEY: Optional[str] = None
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        
        # Auto-configure database URL based on environment
        if not self.DATABASE_URL:
            if self.ENVIRONMENT == "production" or os.getenv("RENDER"):
                # In production (Render), use PostgreSQL from environment
                self.DATABASE_URL = os.getenv("DATABASE_URL", "")
                if self.DATABASE_URL.startswith("postgres://"):
                    # Render uses postgres://, but SQLAlchemy needs postgresql://
                    self.DATABASE_URL = self.DATABASE_URL.replace("postgres://", "postgresql://", 1)
            else:
                # In development, use SQLite
                self.DATABASE_URL = "sqlite:///./xrp_bot.db"
                print(f"Using SQLite for local development: {self.DATABASE_URL}")
        
        # Auto-generate encryption key if not set
        if not self.ENCRYPTION_KEY:
            self.ENCRYPTION_KEY = self.generate_encryption_key()
            print(f"⚠️  Generated ENCRYPTION_KEY: {self.ENCRYPTION_KEY}")
            print("   Add this to your .env file!")
    
    @staticmethod
    def generate_encryption_key() -> str:
        """Generate a new Fernet encryption key"""
        from cryptography.fernet import Fernet
        return Fernet.generate_key().decode()
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings()