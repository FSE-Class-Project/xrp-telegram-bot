import os

from pydantic import Field  # type: ignore[import-not-found]
from pydantic_settings import BaseSettings, SettingsConfigDict  # type: ignore[import-not-found]


class Settings(BaseSettings):
    """Application configuration using Pydantic v2."""

    model_config = SettingsConfigDict(
        env_file=[".env.local", ".env.development", ".env"],
        case_sensitive=True,
        extra="ignore",  # Ignore extra fields to avoid validation errors
    )

    # Application
    APP_NAME: str = "XRP Telegram Bot"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = Field(default=False)
    ENVIRONMENT: str = Field(default="development")

    # Database - Auto-detect based on environment
    DATABASE_URL: str = Field(default="")

    # Security - these should be overridden via environment variables
    ENCRYPTION_KEY: str = Field(default="")
    JWT_SECRET: str = Field(default="")
    JWT_ALGORITHM: str = Field(default="HS256")
    JWT_EXPIRATION_HOURS: int = Field(default=24)
    BOT_API_KEY: str = Field(default="")
    ADMIN_API_KEY: str = Field(default="")

    # Telegram
    TELEGRAM_BOT_TOKEN: str = Field(default="")
    TELEGRAM_WEBHOOK_URL: str | None = Field(default=None)
    TELEGRAM_WEBHOOK_SECRET: str = Field(default="")

    # XRP Ledger
    XRP_NETWORK: str = Field(default="testnet")
    XRP_WEBSOCKET_URL: str = Field(default="wss://s.altnet.rippletest.net:51233")
    XRP_JSON_RPC_URL: str = Field(default="https://s.altnet.rippletest.net:51234")
    XRP_FAUCET_URL: str = Field(default="https://faucet.altnet.rippletest.net/accounts")
    XRP_AUTO_FUND_NEW_WALLETS: bool = Field(default=True)  # Whether to auto-fund new wallets

    # API
    API_HOST: str = Field(default="127.0.0.1")
    API_PORT: int = Field(default=8000)
    API_URL: str = Field(default="http://localhost:8000")
    API_PREFIX: str = Field(default="/api/v1")

    # Redis (optional)
    REDIS_URL: str | None = Field(default=None)
    CACHE_TTL: int = Field(default=300)  # 5 minutes

    # Sentry (monitoring)
    SENTRY_DSN: str | None = Field(default=None)
    SENTRY_ENVIRONMENT: str | None = Field(default=None)

    # External APIs
    PRICE_API_URL: str = Field(default="https://api.coingecko.com/api/v3")
    PRICE_API_KEY: str | None = Field(default=None)

    def __init__(self, **kwargs):
        """Initialize settings with backward compatibility."""
        # Handle WEBHOOK_URL -> TELEGRAM_WEBHOOK_URL mapping
        if "WEBHOOK_URL" in kwargs and "TELEGRAM_WEBHOOK_URL" not in kwargs:
            kwargs["TELEGRAM_WEBHOOK_URL"] = kwargs.pop("WEBHOOK_URL")

        super().__init__(**kwargs)

    def configure_for_environment(self) -> None:
        """Configure settings based on environment - call this explicitly after creation."""
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
                # Also set webhook URL if not already set
                if not self.TELEGRAM_WEBHOOK_URL:
                    self.TELEGRAM_WEBHOOK_URL = render_url

        # Handle legacy WEBHOOK_URL environment variable
        if not self.TELEGRAM_WEBHOOK_URL and os.getenv("WEBHOOK_URL"):
            self.TELEGRAM_WEBHOOK_URL = os.getenv("WEBHOOK_URL")

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

        # Set Sentry environment if not explicitly set
        if not self.SENTRY_ENVIRONMENT:
            self.SENTRY_ENVIRONMENT = self.ENVIRONMENT

    def ensure_encryption_key(self) -> str:
        """Ensure encryption key exists, generate if needed."""
        if not self.ENCRYPTION_KEY:
            self.ENCRYPTION_KEY = self.generate_encryption_key()
            return self.ENCRYPTION_KEY
        return self.ENCRYPTION_KEY

    def _configure_security_settings(self) -> None:
        """Configure security settings based on environment."""
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
            # In production, generate if not provided (but warn about it)
            if not self.JWT_SECRET:
                self.JWT_SECRET = secrets.token_urlsafe(32)
                print("WARNING: Generated JWT_SECRET - should be set via environment variable")
            if not self.BOT_API_KEY:
                self.BOT_API_KEY = secrets.token_urlsafe(32)
                print("WARNING: Generated BOT_API_KEY - should be set via environment variable")
            if not self.ADMIN_API_KEY:
                self.ADMIN_API_KEY = secrets.token_urlsafe(32)
                print("WARNING: Generated ADMIN_API_KEY - should be set via environment variable")
            if not self.TELEGRAM_WEBHOOK_SECRET:
                self.TELEGRAM_WEBHOOK_SECRET = secrets.token_urlsafe(32)

    @staticmethod
    def generate_encryption_key() -> str:
        """Generate a new Fernet encryption key."""
        from cryptography.fernet import Fernet

        return Fernet.generate_key().decode()

    @staticmethod
    def generate_secure_secret(length: int = 32) -> str:
        """Generate a secure random secret."""
        import secrets

        return secrets.token_urlsafe(length)


# Create settings instance
settings = Settings()


def initialize_settings():
    """Initialize and configure settings - must be called before using settings."""
    settings.configure_for_environment()
    return settings
