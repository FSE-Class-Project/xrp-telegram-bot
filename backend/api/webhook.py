"""Telegram webhook endpoint for production deployment."""

import logging
from typing import Any

from fastapi import APIRouter, BackgroundTasks, HTTPException, Request
from fastapi.responses import JSONResponse
from telegram import Update
from telegram.ext import Application

logger = logging.getLogger(__name__)

# Global application instance (will be set by the main backend)
telegram_app: Application | None = None

# Create webhook router
webhook_router = APIRouter(prefix="/webhook", tags=["Webhook"])


def set_telegram_app(app: Application) -> None:
    """Set the Telegram application instance for webhook handling."""
    global telegram_app
    telegram_app = app
    logger.info("Telegram application instance set for webhook handling")


@webhook_router.post("/{bot_token}")
async def telegram_webhook(
    bot_token: str, request: Request, background_tasks: BackgroundTasks
) -> JSONResponse:
    """
    Handle incoming Telegram webhook updates.

    Args:
        bot_token: Bot token from URL path
        request: FastAPI request object
        background_tasks: Background task handler

    Returns:
        JSON response indicating success/failure
    """
    try:
        # Validate that we have a telegram app instance
        if not telegram_app:
            logger.error("Telegram application not initialized")
            raise HTTPException(status_code=503, detail="Telegram bot not ready")

        # Validate bot token
        expected_token = telegram_app.bot.token
        if bot_token != expected_token:
            logger.warning(f"Invalid bot token received: {bot_token[:10]}...")
            raise HTTPException(status_code=401, detail="Invalid bot token")

        # Parse the update
        try:
            update_data = await request.json()
            logger.debug(f"Received webhook update: {update_data}")
        except Exception as e:
            logger.error(f"Failed to parse webhook JSON: {e}")
            raise HTTPException(status_code=400, detail="Invalid JSON") from e

        # Create Telegram Update object
        try:
            update = Update.de_json(update_data, telegram_app.bot)
            if not update:
                logger.warning("Failed to parse Telegram update")
                raise HTTPException(status_code=400, detail="Invalid update format")
        except Exception as e:
            logger.error(f"Failed to create Update object: {e}")
            raise HTTPException(status_code=400, detail="Invalid update structure") from e

        # Process update in background to avoid blocking the webhook response
        background_tasks.add_task(process_update, update)

        # Return success response quickly
        return JSONResponse({"ok": True}, status_code=200)

    except HTTPException:
        # Re-raise HTTP exceptions
        raise
    except Exception as e:
        logger.error(f"Unexpected error in webhook handler: {e}", exc_info=True)
        raise HTTPException(status_code=500, detail="Internal server error") from e


async def process_update(update: Update) -> None:
    """
    Process a Telegram update in the background.

    Args:
        update: Telegram Update object
    """
    try:
        if not telegram_app:
            logger.error("Telegram application not available for update processing")
            return

        # Process the update using the application's update queue
        await telegram_app.process_update(update)
        logger.debug(f"Successfully processed update {update.update_id}")

    except Exception as e:
        logger.error(f"Error processing Telegram update {update.update_id}: {e}", exc_info=True)


@webhook_router.get("/health")
async def webhook_health() -> dict[str, Any]:
    """
    Health check endpoint for the webhook service.

    Returns:
        Health status information
    """
    is_healthy = telegram_app is not None

    return {
        "status": "healthy" if is_healthy else "unhealthy",
        "service": "telegram-webhook",
        "telegram_app_ready": is_healthy,
        "bot_username": telegram_app.bot.username if telegram_app else None,
    }


@webhook_router.get("/info")
async def webhook_info() -> dict[str, Any]:
    """
    Get webhook information and status.

    Returns:
        Webhook configuration info
    """
    if not telegram_app:
        return {"error": "Telegram application not initialized"}

    try:
        # Get current webhook info from Telegram
        webhook_info = await telegram_app.bot.get_webhook_info()

        return {
            "webhook_url": webhook_info.url,
            "has_custom_certificate": webhook_info.has_custom_certificate,
            "pending_update_count": webhook_info.pending_update_count,
            "last_error_date": webhook_info.last_error_date,
            "last_error_message": webhook_info.last_error_message,
            "max_connections": webhook_info.max_connections,
            "allowed_updates": webhook_info.allowed_updates,
        }
    except Exception as e:
        logger.error(f"Failed to get webhook info: {e}")
        return {"error": str(e)}


# Webhook management endpoints (for debugging/administration)
@webhook_router.delete("/{bot_token}")
async def delete_webhook(bot_token: str) -> dict[str, Any]:
    """
    Delete the current webhook (for debugging purposes).

    Args:
        bot_token: Bot token for verification

    Returns:
        Deletion status
    """
    try:
        if not telegram_app:
            raise HTTPException(status_code=503, detail="Telegram bot not ready")

        # Validate bot token
        if bot_token != telegram_app.bot.token:
            raise HTTPException(status_code=401, detail="Invalid bot token")

        # Delete webhook
        await telegram_app.bot.delete_webhook(drop_pending_updates=True)
        logger.info("Webhook deleted successfully")

        return {"ok": True, "message": "Webhook deleted"}

    except Exception as e:
        logger.error(f"Failed to delete webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e)) from e
