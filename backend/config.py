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
    
    # Database
    DATABASE_URL: str = "sqlite:///./xrp_bot.db"
    
    # Security
    ENCRYPTION_KEY: str = ""
    JWT_SECRET: str = ""
    
    # Telegram
    TELEGRAM_BOT_TOKEN: str = ""
    
    # XRP Ledger
    XRP_NETWORK: str = "testnet"
    XRP_WEBSOCKET_URL: str = "wss://s.altnet.rippletest.net:51233"
    
    # API
    API_HOST: str = "0.0.0.0"
    API_PORT: int = 8000
    API_URL: str = "http://localhost:8000"
    
    class Config:
        env_file = ".env"
        case_sensitive = True

# Create settings instance
settings = Settings()
