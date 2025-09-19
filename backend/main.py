"""Main FastAPI application with integrated Telegram webhook support."""

import logging
import os
from contextlib import asynccontextmanager

import uvicorn  # type: ignore
from fastapi import FastAPI, Request  # type: ignore
from fastapi.middleware.cors import CORSMiddleware  # type: ignore
from fastapi.responses import JSONResponse  # type: ignore
from telegram.ext import Application

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

# Global reference to Telegram app for cleanup
telegram_app_instance = None


@asynccontextmanager
async def lifespan(app: FastAPI):  # noqa: ARG001
    """Manage application lifecycle."""
    global telegram_app_instance

    # Initialize settings first
    initialize_settings()

    # Initialize Sentry for error tracking (production)
    if settings.SENTRY_DSN and settings.ENVIRONMENT == "production":
        try:
            from .utils.monitoring import init_sentry

            init_sentry(
                settings.SENTRY_DSN,
                settings.SENTRY_ENVIRONMENT or settings.ENVIRONMENT,
            )
            logger.info("✅ Sentry error tracking initialized")
        except Exception as e:
            logger.error(f"⚠️ Sentry initialization failed: {e}")

    # Initialize Redis cache service
    try:
        from .services.cache_service import get_cache_service

        cache = get_cache_service()
        if cache.enabled:
            logger.info("✅ Redis cache service initialized successfully")
        else:
            logger.warning("⚠️ Redis cache service running in degraded mode")
    except Exception as e:
        logger.error(f"⚠️ Cache service initialization failed: {e}")

    # Startup
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"🌍 Environment: {settings.ENVIRONMENT}")
    logger.info(f"🐛 Debug mode: {settings.DEBUG}")
    logger.info(f"🌐 API URL: {settings.API_URL}")
    logger.info(f"💾 Database: {settings.DATABASE_URL[:30]}...")
    logger.info(f"🪙 XRP Network: {settings.XRP_NETWORK}")
    if settings.REDIS_URL:
        logger.info(f"🔴 Redis: {settings.REDIS_URL[:30]}...")
    if settings.SENTRY_DSN:
        logger.info("🐛 Sentry: Configured for error tracking")

    # Initialize database engine and schema
    try:
        initialize_database_engine(settings.DATABASE_URL, settings.DEBUG)
        init_database()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        if settings.ENVIRONMENT == "production":
            raise

    # Initialize encryption service
    try:
        encryption_key = settings.ensure_encryption_key()
        if encryption_key == settings.ENCRYPTION_KEY and not os.getenv("ENCRYPTION_KEY"):
            if settings.ENVIRONMENT == "production":
                logger.error("❌ ENCRYPTION_KEY must be set in production environment!")
                raise ValueError("ENCRYPTION_KEY required in production")
            else:
                logger.warning("⚠️ Generated new ENCRYPTION_KEY - add this to your .env file!")
                logger.info(f"   ENCRYPTION_KEY={encryption_key[:8]}...{encryption_key[-4:]}")

        from .utils.encryption import encryption_service

        encryption_service.generate_key()
        logger.info("✅ Encryption service initialized")
    except Exception as e:
        logger.error(f"❌ Encryption initialization failed: {e}")
        if settings.ENVIRONMENT == "production":
            raise

    # Test XRP connection
    try:
        logger.info(f"✅ XRP Service initialized for {settings.XRP_NETWORK}")
    except Exception as e:
        logger.error(f"⚠️ XRP Service initialization warning: {e}")

    # Initialize Telegram bot for webhooks if in production/Render
    if (IS_RENDER or settings.ENVIRONMENT == "production") and settings.TELEGRAM_BOT_TOKEN:
        try:
            logger.info("🤖 Initializing Telegram bot for webhook mode...")

            # Create Telegram application
            telegram_app_instance = Application.builder().token(settings.TELEGRAM_BOT_TOKEN).build()

            # Setup bot data
            telegram_app_instance.bot_data["api_url"] = settings.API_URL
            telegram_app_instance.bot_data["api_key"] = settings.BOT_API_KEY

            # Import and setup handlers from bot module
            try:
                from bot.main import setup_handlers

                setup_handlers(telegram_app_instance)
                logger.info("✅ Bot handlers configured")
            except ImportError as e:
                logger.error(f"❌ Failed to import bot handlers: {e}")
                logger.warning("⚠️ Bot handlers not available - basic webhook mode only")

            # Initialize the application
            await telegram_app_instance.initialize()
            await telegram_app_instance.start()

            # Set the app instance for webhook handling
            set_telegram_app(telegram_app_instance)

            # Set up webhook
            webhook_url = None
            if os.getenv("RENDER_EXTERNAL_URL"):
                webhook_url = (
                    f"{os.getenv('RENDER_EXTERNAL_URL')}/webhook/{settings.TELEGRAM_BOT_TOKEN}"
                )
            elif settings.TELEGRAM_WEBHOOK_URL:
                webhook_url = (
                    f"{settings.TELEGRAM_WEBHOOK_URL}/webhook/{settings.TELEGRAM_BOT_TOKEN}"
                )
            elif settings.API_URL:
                webhook_url = f"{settings.API_URL}/webhook/{settings.TELEGRAM_BOT_TOKEN}"

            if webhook_url:
                await telegram_app_instance.bot.set_webhook(
                    url=webhook_url,
                    secret_token=(
                        settings.TELEGRAM_WEBHOOK_SECRET
                        if settings.TELEGRAM_WEBHOOK_SECRET
                        else None
                    ),
                    drop_pending_updates=True,
                    allowed_updates=[
                        "message",
                        "callback_query",
                        "inline_query",
                    ],
                )
                logger.info(f"✅ Webhook set to: {webhook_url}")

                # Verify webhook was set
                webhook_info = await telegram_app_instance.bot.get_webhook_info()
                if webhook_info.url:
                    logger.info(f"✅ Webhook verified: {webhook_info.url}")
                    if webhook_info.last_error_message:
                        logger.warning(f"⚠️ Last webhook error: {webhook_info.last_error_message}")
                else:
                    logger.error("❌ Webhook URL not set properly")
            else:
                logger.warning("⚠️ No webhook URL configured - bot will not receive updates")

        except Exception as e:
            logger.error(f"❌ Telegram bot initialization failed: {e}")
            if settings.ENVIRONMENT == "production":
                raise
    elif settings.ENVIRONMENT == "development":
        logger.info("💻 Development mode - bot should be run separately with polling")
    else:
        logger.warning("⚠️ Telegram bot not initialized - missing TELEGRAM_BOT_TOKEN")

    yield

    # Shutdown
    logger.info("👋 Shutting down application...")

    # Cleanup Telegram app if initialized
    if telegram_app_instance:
        try:
            logger.info("🤖 Shutting down Telegram bot...")
            await telegram_app_instance.stop()
            await telegram_app_instance.shutdown()
            logger.info("✅ Telegram bot shutdown completed")
        except Exception as e:
            logger.error(f"⚠️ Telegram bot shutdown warning: {e}")

    close_database_connections()
    logger.info("✅ Application shutdown completed")


# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan,
)

# Add CORS middleware with environment-specific configuration
if settings.ENVIRONMENT == "production":
    # Production: Restrictive CORS
    allowed_origins = [settings.API_URL]

    # Add Render URL if available
    render_url = os.getenv("RENDER_EXTERNAL_URL")
    if render_url and render_url not in allowed_origins:
        allowed_origins.append(render_url)

    app.add_middleware(
        CORSMiddleware,
        allow_origins=allowed_origins,
        allow_credentials=False,
        allow_methods=["GET", "POST", "PUT", "DELETE"],
        allow_headers=[
            "Content-Type",
            "Authorization",
            "X-API-Key",
            "X-Idempotency-Key",
        ],
    )
else:
    # Development: Permissive CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

# Setup rate limiting
if settings.ENVIRONMENT == "production":
    rate_limits = ["100/minute", "1000/hour"]
else:
    rate_limits = ["200/minute", "2000/hour"]

setup_rate_limiting(app, default_limits=rate_limits)

# Add idempotency middleware
add_idempotency_middleware(app)


# Add monitoring middleware
@app.middleware("http")
async def monitoring_middleware(request: Request, call_next):
    """Middleware for monitoring and metrics collection."""
    import time

    from .utils.monitoring import metrics

    start_time = time.time()

    try:
        response = await call_next(request)
        duration = time.time() - start_time

        # Record request metrics
        metrics.record_request(
            endpoint=str(request.url.path),
            method=request.method,
            status_code=response.status_code,
            duration=duration,
        )

        # Add performance headers for monitoring
        response.headers["X-Process-Time"] = str(duration)
        response.headers["X-Service-Version"] = settings.APP_VERSION

        return response

    except Exception as e:
        duration = time.time() - start_time

        # Record error metrics
        metrics.record_error(error_type=type(e).__name__, endpoint=str(request.url.path))

        # Re-raise the exception
        raise


# Include API routes
app.include_router(router)
app.include_router(webhook_router)
app.include_router(settings_router)


# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):  # noqa: ARG001
    """Global exception handler."""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={"detail": str(exc) if settings.DEBUG else "Internal server error"},
    )


# Root endpoint
@app.get("/")
async def root():
    """Root endpoint."""
    return {
        "message": "XRP Telegram Bot API",
        "version": settings.APP_VERSION,
        "docs": "/docs",
        "health": "/api/v1/health",
        "environment": settings.ENVIRONMENT,
        "network": settings.XRP_NETWORK,
        "platform": "render" if IS_RENDER else "local",
        "webhook_configured": telegram_app_instance is not None,
        "build_timestamp": "2025-09-16",  # Update this to force cache refresh
    }


# Health check endpoint for Render
@app.get("/health")
async def health():
    """Health check endpoint for monitoring."""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "telegram_bot": "ready" if telegram_app_instance else "not_initialized",
    }


# Comprehensive health check endpoint
@app.get("/api/v1/health")
async def detailed_health():
    """Detailed health check endpoint."""
    from .database.connection import get_db
    from .utils.monitoring import HealthChecker

    # Get database session for health checks
    db_gen = get_db()
    db = next(db_gen)

    try:
        # Get comprehensive health status
        health_status = await HealthChecker.get_full_health_status(db)

        # Add Redis cache status
        try:
            from .services.cache_service import get_cache_service

            cache = get_cache_service()
            health_status["services"]["redis"] = cache.health_check()
        except Exception as e:
            health_status["services"]["redis"] = {
                "connected": False,
                "error": str(e),
            }

        # Add Sentry status
        health_status["services"]["sentry"] = {
            "configured": bool(settings.SENTRY_DSN),
            "environment": settings.SENTRY_ENVIRONMENT,
        }

        # Determine overall status
        services = health_status["services"]
        overall_status = "healthy"

        # Check if any critical services are down
        if services["database"]["status"] == "unhealthy":
            overall_status = "unhealthy"
        elif services["xrp_ledger"]["status"] == "unhealthy" or not services["redis"]["connected"]:
            overall_status = "degraded"

        health_status["overall_status"] = overall_status

        return health_status

    finally:
        db.close()


# Webhook test endpoint (development/debugging only)
if settings.DEBUG:

    @app.get("/webhook/info")
    async def webhook_info():
        """Get current webhook configuration (debug only)."""
        if not telegram_app_instance:
            return {"error": "Telegram bot not initialized"}

        try:
            info = await telegram_app_instance.bot.get_webhook_info()
            return {
                "url": info.url,
                "has_custom_certificate": info.has_custom_certificate,
                "pending_update_count": info.pending_update_count,
                "last_error_date": info.last_error_date,
                "last_error_message": info.last_error_message,
                "max_connections": info.max_connections,
                "allowed_updates": info.allowed_updates,
                "ip_address": info.ip_address,
            }
        except Exception as e:
            return {"error": str(e)}


# Run application
if __name__ == "__main__":
    # Determine if we're on Render
    if IS_RENDER:
        logger.info("🚀 Running on Render platform")
        # Render will handle running the app via the start command
        # The app is already created, so Render's uvicorn will pick it up
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
