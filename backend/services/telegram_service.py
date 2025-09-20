"""Telegram bot service for webhook mode integration."""

from __future__ import annotations

import logging
import os

from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters,
)

logger = logging.getLogger(__name__)


async def create_telegram_application() -> Application | None:
    """Create and configure a Telegram application for webhook mode.

    Returns
    -------
        Configured Telegram Application instance or None if failed

    """
    bot_token = os.getenv("TELEGRAM_BOT_TOKEN")
    if not bot_token:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables")
        return None

    try:
        # Import bot handlers
        from bot.handlers.price import price_command
        from bot.handlers.start import help_command, start_command
        from bot.handlers.transaction import (
            ADDRESS,
            AMOUNT,
            CONFIRM,
            address_handler,
            amount_handler,
            cancel_handler,
            confirm_handler,
            history_command,
            send_command,
        )
        from bot.handlers.wallet import balance_command, profile_command

        # Create application
        application = Application.builder().token(bot_token).build()

        # Set bot data
        api_url = os.getenv("API_URL", "http://localhost:8000")
        api_key = os.getenv("BOT_API_KEY", "dev-bot-api-key-change-in-production")

        application.bot_data["api_url"] = api_url
        application.bot_data["api_key"] = api_key

        # Conversation handler for the /send command
        send_conversation_handler = ConversationHandler(
            entry_points=[CommandHandler("send", send_command)],
            states={
                AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount_handler)],
                ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_handler)],
                CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_handler)],
            },
            fallbacks=[CommandHandler("cancel", cancel_handler)],
        )

        # Add all handlers
        application.add_handler(CommandHandler("start", start_command))
        application.add_handler(CommandHandler("help", help_command))
        application.add_handler(CommandHandler("balance", balance_command))
        application.add_handler(CommandHandler("price", price_command))
        application.add_handler(CommandHandler("profile", profile_command))
        application.add_handler(CommandHandler("history", history_command))
        application.add_handler(send_conversation_handler)

        # Add callback query handler if keyboards are available
        try:
            from bot.main import callback_query_handler

            application.add_handler(CallbackQueryHandler(callback_query_handler))
        except ImportError:
            logger.warning("Keyboard handlers not available, skipping callback query handler")

        # Add error handler
        async def error_handler(update, context):
            """Log errors."""
            logger.error(
                f'Webhook update "{update}" caused error "{context.error}"',
                exc_info=context.error,
            )

        application.add_error_handler(error_handler)

        logger.info("✅ Telegram application created and configured")
        return application

    except Exception as e:
        logger.error(f"❌ Failed to create Telegram application: {e}", exc_info=True)
        return None


async def setup_webhook(application: Application, webhook_url: str) -> bool:
    """Set up webhook for the Telegram bot.

    Args:
    ----
        application: Telegram Application instance
        webhook_url: URL where Telegram should send updates

    Returns:
    -------
        True if webhook was set successfully, False otherwise

    """
    try:
        await application.bot.set_webhook(
            url=webhook_url,
            allowed_updates=["message", "callback_query"],
            drop_pending_updates=True,
            max_connections=40,  # Render allows up to 40 connections
            secret_token=None,  # Can add for additional security
        )

        # Verify webhook was set
        webhook_info = await application.bot.get_webhook_info()
        if webhook_info.url == webhook_url:
            logger.info(f"✅ Webhook set successfully: {webhook_url}")
            logger.info(f"📊 Webhook info: {webhook_info.pending_update_count} pending updates")
            return True
        else:
            logger.error(
                f"❌ Webhook verification failed. Expected: {webhook_url}, Got: {webhook_info.url}"
            )
            return False

    except Exception as e:
        logger.error(f"❌ Failed to set webhook: {e}", exc_info=True)
        return False


async def delete_webhook(application: Application) -> bool:
    """Delete the current webhook.

    Args:
    ----
        application: Telegram Application instance

    Returns:
    -------
        True if webhook was deleted successfully, False otherwise

    """
    try:
        await application.bot.delete_webhook(drop_pending_updates=True)
        logger.info("✅ Webhook deleted successfully")
        return True
    except Exception as e:
        logger.error(f"❌ Failed to delete webhook: {e}", exc_info=True)
        return False
