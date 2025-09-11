import os

from pydantic_settings import BaseSettings


class Settings(BaseSettings):
    """Application configuration using Pydantic"""

    # Application
    APP_NAME: str = "XRP Telegram Bot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    ENVIRONMENT: str = "development"

    # Database - Auto-detect based on environment
    DATABASE_URL: str = ""

    # Security - these should be overridden via environment variables
    ENCRYPTION_KEY: str = ""
    JWT_SECRET: str = ""
    JWT_ALGORITHM: str = "HS256"
    JWT_EXPIRATION_HOURS: int = 24
    BOT_API_KEY: str = ""
    ADMIN_API_KEY: str = ""

    # Telegram
    TELEGRAM_BOT_TOKEN: str
    TELEGRAM_WEBHOOK_URL: str | None = None
    TELEGRAM_WEBHOOK_SECRET: str = ""

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
    REDIS_URL: str | None = None
    CACHE_TTL: int = 300  # 5 minutes

    # External APIs
    PRICE_API_URL: str = "https://api.coingecko.com/api/v3"
    PRICE_API_KEY: str | None = None

    def configure_for_environment(self) -> None:
        """Configure settings based on environment - call this explicitly after creation"""
        # Auto-configure for Render deployment
        if os.getenv("RENDER"):
            self.ENVIRONMENT = "production"
            self.DEBUG = False
            # Use Render's provided port or default
            self.API_PORT = int(os.getenv("PORT", 10000))
            # Use external URL for API if available
            render_url = os.getenv("RENDER_EXTERNAL_URL")
            if render_url:
                self.API_URL = render_url

        # Auto-configure database URL based on environment
        if not self.DATABASE_URL:
            if self.ENVIRONMENT == "production" or os.getenv("RENDER"):
                # In production (Render), use PostgreSQL from environment
                self.DATABASE_URL = os.getenv("DATABASE_URL", "")
                if self.DATABASE_URL.startswith("postgres://"):
                    # Render uses postgres://, but SQLAlchemy needs postgresql://
                    self.DATABASE_URL = self.DATABASE_URL.replace("postgres://", "postgresql://", 1)
                if not self.DATABASE_URL:
                    raise ValueError("DATABASE_URL must be set in production environment")
            else:
                # In development, use SQLite
                self.DATABASE_URL = "sqlite:///./xrp_bot.db"
        
        # Configure security settings based on environment
        self._configure_security_settings()

    def ensure_encryption_key(self) -> str:
        """Ensure encryption key exists, generate if needed"""
        if not self.ENCRYPTION_KEY:
            self.ENCRYPTION_KEY = self.generate_encryption_key()
            return self.ENCRYPTION_KEY
        return self.ENCRYPTION_KEY

    def _configure_security_settings(self) -> None:
        """Configure security settings based on environment"""
        import secrets
        
        # Generate development defaults if in development mode
        if self.ENVIRONMENT != "production" and not os.getenv("RENDER"):
            if not self.JWT_SECRET:
                self.JWT_SECRET = f"dev-jwt-{secrets.token_urlsafe(16)}"
            if not self.BOT_API_KEY:
                self.BOT_API_KEY = f"dev-bot-{secrets.token_urlsafe(16)}"
            if not self.ADMIN_API_KEY:
                self.ADMIN_API_KEY = f"dev-admin-{secrets.token_urlsafe(16)}"
            if not self.TELEGRAM_WEBHOOK_SECRET:
                self.TELEGRAM_WEBHOOK_SECRET = f"dev-webhook-{secrets.token_urlsafe(16)}"
        else:
            # In production, all secrets must be provided via environment
            missing_secrets = []
            if not self.JWT_SECRET:
                missing_secrets.append("JWT_SECRET")
            if not self.BOT_API_KEY:
                missing_secrets.append("BOT_API_KEY")
            if not self.ADMIN_API_KEY:
                missing_secrets.append("ADMIN_API_KEY")
            if not self.TELEGRAM_WEBHOOK_SECRET:
                missing_secrets.append("TELEGRAM_WEBHOOK_SECRET")
                
            if missing_secrets:
                raise ValueError(f"Production environment requires these secrets: {', '.join(missing_secrets)}")

    @staticmethod
    def generate_encryption_key() -> str:
        """Generate a new Fernet encryption key"""
        from cryptography.fernet import Fernet

        return Fernet.generate_key().decode()
    
    @staticmethod
    def generate_secure_secret(length: int = 32) -> str:
        """Generate a secure random secret"""
        import secrets
        return secrets.token_urlsafe(length)

    class Config:
        env_file = ".env"
        case_sensitive = True


# Create settings instance
settings = Settings()

# Configure based on environment (call this explicitly)
def initialize_settings():
    """Initialize and configure settings - must be called before using settings"""
    settings.configure_for_environment()
    return settings
