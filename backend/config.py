"""
Production configuration with enhanced security and monitoring
"""
import os
import secrets
from typing import Optional, List
from pydantic import validator
from backend.config import Settings as BaseSettings

class ProductionSettings(BaseSettings):
    """Production-specific configuration"""
    
    # Force production settings
    ENVIRONMENT: str = "production"
    DEBUG: bool = False
    
    # Security enhancements
    ALLOWED_HOSTS: List[str] = ["api.xrpbot.com", "localhost"]
    CORS_ORIGINS: List[str] = ["https://api.xrpbot.com"]
    SECRET_KEY: str = os.getenv("SECRET_KEY", secrets.token_urlsafe(32))
    
    # Rate limiting
    RATE_LIMIT_ENABLED: bool = True
    RATE_LIMIT_PER_MINUTE: int = 60
    RATE_LIMIT_PER_HOUR: int = 1000
    
    # Monitoring
    SENTRY_DSN: Optional[str] = os.getenv("SENTRY_DSN")
    LOG_LEVEL: str = "INFO"
    
    # Database pool settings for production
    DB_POOL_SIZE: int = 20
    DB_MAX_OVERFLOW: int = 40
    DB_POOL_TIMEOUT: int = 30
    DB_POOL_RECYCLE: int = 3600
    
    # Telegram webhook for production
    TELEGRAM_WEBHOOK_URL: str = os.getenv("TELEGRAM_WEBHOOK_URL", "")
    TELEGRAM_WEBHOOK_PATH: str = "/webhook"
    TELEGRAM_WEBHOOK_SECRET: str = os.getenv("TELEGRAM_WEBHOOK_SECRET", secrets.token_urlsafe(32))
    
    # XRP Ledger MainNet settings (when ready)
    XRP_MAINNET_ENABLED: bool = False
    XRP_MAINNET_URL: str = "wss://xrplcluster.com"
    
    # Backup and recovery
    BACKUP_ENABLED: bool = True
    BACKUP_INTERVAL_HOURS: int = 6
    BACKUP_RETENTION_DAYS: int = 30
    
    # Security headers
    SECURITY_HEADERS: dict = {
        "X-Content-Type-Options": "nosniff",
        "X-Frame-Options": "DENY",
        "X-XSS-Protection": "1; mode=block",
        "Strict-Transport-Security": "max-age=31536000; includeSubDomains",
        "Content-Security-Policy": "default-src 'self'",
    }
    
    # API throttling per user
    MAX_TRANSACTIONS_PER_DAY: int = 100
    MAX_BALANCE_CHECKS_PER_HOUR: int = 60
    
    # Minimum balance requirements
    MIN_XRP_BALANCE: float = 10.0  # Minimum XRP to keep in wallet
    MAX_SEND_AMOUNT: float = 10000.0  # Maximum single transaction
    
    @validator("ENCRYPTION_KEY", pre=True)
    def validate_encryption_key(cls, v):
        """Ensure encryption key is set in production"""
        if not v:
            raise ValueError("ENCRYPTION_KEY must be set in production")
        if len(v) < 32:
            raise ValueError("ENCRYPTION_KEY must be at least 32 characters")
        return v
    
    @validator("TELEGRAM_BOT_TOKEN", pre=True)
    def validate_bot_token(cls, v):
        """Ensure bot token is set in production"""
        if not v:
            raise ValueError("TELEGRAM_BOT_TOKEN must be set in production")
        return v
    
    @validator("DATABASE_URL", pre=True)
    def validate_database_url(cls, v):
        """Ensure proper database in production"""
        if not v or "sqlite" in v.lower():
            raise ValueError("Production must use PostgreSQL, not SQLite")
        return v
    
    class Config:
        env_file = ".env.production"
        case_sensitive = True

# Create production settings instance
if os.getenv("ENVIRONMENT") == "production":
    settings = ProductionSettings()
else:
    from backend.config import settings