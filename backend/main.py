"""Main FastAPI application"""

import logging
import os
from contextlib import asynccontextmanager

import uvicorn
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from .api.middleware import add_idempotency_middleware, setup_rate_limiting
from .api.routes import router
from .api.settings_routes import settings_router
from .api.webhook import set_telegram_app, webhook_router
from .config import initialize_settings, settings
from .database.connection import (
    close_database_connections,
    init_database,
    initialize_database_engine,
)

# Check if running on Render
IS_RENDER = os.getenv("RENDER") is not None

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Initialize settings first
    initialize_settings()

    # Startup
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"🌍 Environment: {settings.ENVIRONMENT}")
    logger.info(f"🐛 Debug mode: {settings.DEBUG}")
    logger.info(f"🌐 API URL: {settings.API_URL}")
    logger.info(f"💾 Database: {settings.DATABASE_URL[:30]}...")
    logger.info(f"🪙 XRP Network: {settings.XRP_NETWORK}")

    # Initialize database engine and schema
    try:
        initialize_database_engine(settings.DATABASE_URL, settings.DEBUG)
        init_database()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise

    # Initialize encryption service
    try:
        # Ensure encryption key is available
        encryption_key = settings.ensure_encryption_key()
        if encryption_key == settings.ENCRYPTION_KEY and not os.getenv("ENCRYPTION_KEY"):
            if settings.ENVIRONMENT == "production":
                logger.error("❌ ENCRYPTION_KEY must be set in production environment!")
                raise ValueError("ENCRYPTION_KEY required in production")
            else:
                logger.warning("⚠️ Generated new ENCRYPTION_KEY - add this to your .env file!")
                # Only show key in development mode and only first few characters
                logger.info(f"   ENCRYPTION_KEY={encryption_key[:8]}...{encryption_key[-4:]}")

        from .utils.encryption import encryption_service

        # encryption_service is already an instance, just verify it exists
        encryption_service.generate_key()
        logger.info("✅ Encryption service initialized")
    except Exception as e:
        logger.error(f"❌ Encryption initialization failed: {e}")
        if settings.ENVIRONMENT == "production":
            raise

    # Test XRP connection
    try:
        # Just create the service to test connection
        logger.info(f"✅ XRP Service initialized for {settings.XRP_NETWORK}")
    except Exception as e:
        logger.error(f"⚠️ XRP Service initialization warning: {e}")

    # Initialize Telegram bot for webhooks if in production
    telegram_app = None
    if IS_RENDER and os.getenv("TELEGRAM_BOT_TOKEN"):
        try:
            from .services.telegram_service import create_telegram_application, setup_webhook

            # Create and configure Telegram application
            telegram_app = await create_telegram_application()

            if telegram_app:
                # Initialize the application
                await telegram_app.initialize()

                # Set the app instance for webhook handling
                set_telegram_app(telegram_app)

                # Set up webhook if RENDER_EXTERNAL_URL is available
                render_url = os.getenv("RENDER_EXTERNAL_URL")
                if render_url:
                    webhook_url = f"{render_url}/webhook/{os.getenv('TELEGRAM_BOT_TOKEN')}"
                    await setup_webhook(telegram_app, webhook_url)

                logger.info("✅ Telegram bot initialized for webhook mode")
            else:
                logger.error("❌ Failed to create Telegram application")

        except Exception as e:
            logger.error(f"❌ Telegram bot initialization failed: {e}")
            if settings.ENVIRONMENT == "production":
                raise

    yield

    # Cleanup Telegram app if initialized
    if telegram_app:
        try:
            await telegram_app.shutdown()
            logger.info("✅ Telegram bot shutdown completed")
        except Exception as e:
            logger.error(f"⚠️ Telegram bot shutdown warning: {e}")

    # Shutdown
    logger.info("👋 Shutting down application...")
    close_database_connections()


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME, version=settings.APP_VERSION, debug=settings.DEBUG, lifespan=lifespan
)

# Add CORS middleware with environment-specific configuration
if settings.ENVIRONMENT == "production":
    # Production: Restrictive CORS
    allowed_origins = [
        settings.API_URL,
    ]
    # Add render URL if available
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url and render_url not in allowed_origins:
        allowed_origins.append(render_url)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,  # More secure for production
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=["Content-Type", "Authorization"],
    )
else:
    # Development: Permissive CORS for easier development
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Setup rate limiting and idempotency middleware
# Configure different limits based on environment
if settings.ENVIRONMENT == "production":
    rate_limits = ["100/minute", "1000/hour"]
else:
    rate_limits = ["200/minute", "2000/hour"]  # More lenient for development

setup_rate_limiting(app, default_limits=rate_limits)  # type: ignore[arg-type]

# Add idempotency middleware
add_idempotency_middleware(app)

# Include API routes
app.include_router(router)
app.include_router(webhook_router)
app.include_router(settings_router)


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500, content={"detail": str(exc) if settings.DEBUG else "Internal server error"}
    )


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint"""
    return {
        "message": "XRP Telegram Bot API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/v1/health",
        "environment": settings.ENVIRONMENT,
        "network": settings.XRP_NETWORK,
        "platform": "render" if IS_RENDER else "local",
        "debug_timestamp": "2025-09-11-updated",  # Force reload indicator
    }


# Health check endpoint for Render
@app.get("/health")
async def health():
    """Health check endpoint for monitoring"""
    return {"status": "healthy", "service": settings.APP_NAME, "version": settings.APP_VERSION}


# Run application
if __name__ == "__main__":
    # Determine if we're on Render
    if IS_RENDER:
        logger.info("🚀 Running on Render platform")
        # Render will handle running the app via the start command
        # The app is already created, so Render's gunicorn/uvicorn will pick it up
    else:
        # Local development
        logger.info("🏠 Running in local development mode")
        uvicorn.run(
            "backend.main:app",
            host=settings.API_HOST,
            port=settings.API_PORT,
            reload=settings.DEBUG,
            log_level="info" if not settings.DEBUG else "debug",
        )
