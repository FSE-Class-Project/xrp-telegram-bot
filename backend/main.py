"""Main FastAPI application"""
import os
import logging
from contextlib import asynccontextmanager

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
import uvicorn

from .config import settings
from .database.connection import init_database, engine
from .api.routes import router
from .api.middleware import setup_rate_limiting

# Check if running on Render
IS_RENDER = os.getenv("RENDER") is not None

# Configure logging
logging.basicConfig(
    level=logging.INFO if not settings.DEBUG else logging.DEBUG,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger(__name__)

@asynccontextmanager
async def lifespan(app: FastAPI):
    """Manage application lifecycle"""
    # Startup
    logger.info(f"🚀 Starting {settings.APP_NAME} v{settings.APP_VERSION}")
    logger.info(f"🌍 Environment: {settings.ENVIRONMENT}")
    logger.info(f"🐛 Debug mode: {settings.DEBUG}")
    logger.info(f"🌐 API URL: {settings.API_URL}")
    logger.info(f"💾 Database: {settings.DATABASE_URL[:30]}...")
    logger.info(f"🪙 XRP Network: {settings.XRP_NETWORK}")
    
    # Initialize database
    try:
        init_database()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.error(f"❌ Database initialization failed: {e}")
        raise
    
    # Initialize encryption service
    try:
        from .utils.encryption import encryption_service
        # encryption_service is already an instance, just verify it exists
        test_key = encryption_service.generate_key()
        logger.info("✅ Encryption service initialized")
    except Exception as e:
        logger.error(f"❌ Encryption initialization failed: {e}")
        if settings.ENVIRONMENT == "production":
            raise
    
    # Test XRP connection
    try:
        from .services.xrp_service import xrp_service
        # Just create the service to test connection
        logger.info(f"✅ XRP Service initialized for {settings.XRP_NETWORK}")
    except Exception as e:
        logger.error(f"⚠️ XRP Service initialization warning: {e}")
    
    yield
    
    # Shutdown
    logger.info("👋 Shutting down application...")
    engine.dispose()

# Create FastAPI app
app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    debug=settings.DEBUG,
    lifespan=lifespan
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # Configure appropriately for production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Setup rate limiting
# Configure different limits based on environment
if settings.ENVIRONMENT == "production":
    rate_limits = ["100/minute", "1000/hour"]
else:
    rate_limits = ["200/minute", "2000/hour"]  # More lenient for development

setup_rate_limiting(app, default_limits=rate_limits)

# Include API routes
app.include_router(router)

# Exception handler
@app.exception_handler(Exception)
async def global_exception_handler(request: Request, exc: Exception):
    """Global exception handler"""
    logger.error(f"Unhandled exception: {exc}", exc_info=True)
    return JSONResponse(
        status_code=500,
        content={
            "detail": str(exc) if settings.DEBUG else "Internal server error"
        }
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
        "platform": "render" if IS_RENDER else "local"
    }

# Health check endpoint for Render
@app.get("/health")
async def health():
    """Health check endpoint for monitoring"""
    return {
        "status": "healthy",
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION
    }

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
            log_level="info" if not settings.DEBUG else "debug"
        )