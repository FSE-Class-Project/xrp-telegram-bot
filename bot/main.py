import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    CallbackQueryHandler,
    filters,
    ContextTypes,
)
from telegram.constants import ParseMode # Use HTML for consistency
from html import escape
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# --- Configuration ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BOT_API_KEY = os.getenv("BOT_API_KEY", "dev-bot-api-key-change-in-production")
API_URL = os.getenv("API_URL", "http://localhost:8000")
WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")  # Render provides this automatically
PORT = int(os.getenv("PORT", 8443))
ENVIRONMENT = os.getenv("ENVIRONMENT", "development")

# Render detection
IS_RENDER = os.getenv("RENDER") is not None

# --- Import Handlers & Keyboards ---
# These imports will now work because we are creating the files.
from .handlers.start import start_command, help_command
from .handlers.wallet import balance_command, profile_command
from .handlers.transaction import (
    send_command,
    amount_handler,
    address_handler,
    confirm_handler,
    cancel_handler,
    history_command, # This is now defined in transaction.py
    AMOUNT,
    ADDRESS,
    CONFIRM,
)
from .handlers.price import price_command
from .handlers.settings import settings_command
from .keyboards.menus import keyboards # Import the keyboards object

# --- Handlers ---

async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all inline keyboard button presses."""
    query = update.callback_query
    if not query or not query.data:
        return

    # Answer the callback to remove the "loading" state from the button
    await query.answer()

    # Route to appropriate handler based on the button's callback_data
    if query.data == "balance":
        await balance_command(update, context)
    elif query.data == "send":
        await send_command(update, context)
    elif query.data == "price":
        await price_command(update, context)
    elif query.data == "history":
        await history_command(update, context)
    elif query.data == "profile":
        await profile_command(update, context)
    elif query.data == "help":
        await help_command(update, context)
    elif query.data == "main_menu":
        message = "🏠 <b>Main Menu</b>\n\nWhat would you like to do?"
        if query.message:
            await query.message.edit_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboards.main_menu(),
            )
    elif query.data.startswith("refresh_"):
        if query.data == "refresh_balance":
            await balance_command(update, context)
        elif query.data == "refresh_price":
            # Import price refresh handler
            from .handlers.price import price_refresh_callback
            await price_refresh_callback(update, context)
        elif query.data == "refresh_history":
            await history_command(update, context)
    elif query.data == "market_stats":
        # Import market stats handler
        from .handlers.price import market_stats_callback
        await market_stats_callback(update, context)
    elif query.data.startswith(("notification_", "currency_", "security_", "language_", "export_", "delete_", "toggle_", "set_", "setup_")):
        # Handle settings-related callbacks
        from .handlers.settings import (
            notification_settings, currency_settings, security_settings, language_settings,
            export_data, delete_account_warning, toggle_setting, set_currency
        )
        
        if query.data == "notification_settings":
            await notification_settings(update, context)
        elif query.data == "currency_settings":
            await currency_settings(update, context)
        elif query.data == "security_settings":
            await security_settings(update, context)
        elif query.data == "language_settings":
            await language_settings(update, context)
        elif query.data == "export_data":
            await export_data(update, context)
        elif query.data == "delete_account":
            await delete_account_warning(update, context)
        elif query.data.startswith("toggle_"):
            setting_name = query.data[7:]  # Remove "toggle_" prefix
            await toggle_setting(update, context, setting_name)
        elif query.data.startswith("set_currency_"):
            currency = query.data[13:]  # Remove "set_currency_" prefix
            await set_currency(update, context, currency)
    elif query.data == "settings":
        # Handle settings menu
        await settings_command(update, context)
    elif query.data in ["retry", "cancel_send", "confirm_send"]:
        # Handle special callback data
        if query.data == "retry":
            await query.message.edit_text(
                "🔄 <b>Retry</b>\n\nPlease try your last action again.",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboards.main_menu()
            )
        elif query.data == "cancel_send":
            await query.message.edit_text(
                "❌ <b>Transaction Cancelled</b>\n\nTransaction has been cancelled.",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboards.main_menu()
            )
        elif query.data == "confirm_send":
            # Handle transaction confirmation
            logger.info("Transaction confirmation requested")
            await query.message.edit_text(
                "✅ <b>Transaction Confirmed</b>\n\nProcessing your transaction...",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboards.main_menu()
            )

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced error handler with detailed logging and user-friendly messages."""
    error = context.error
    logger.error(f'Update "{update}" caused error "{error}"', exc_info=error)

    if isinstance(update, Update):
        # Determine if this is a callback query or message
        if update.callback_query:
            # Handle callback query errors
            try:
                await update.callback_query.answer(
                    "⚠️ An error occurred. Please try again.", 
                    show_alert=True
                )
            except Exception as e:
                logger.error(f"Failed to answer callback query: {e}")
        
        # Send error message to user
        if update.effective_message:
            from .utils.formatting import format_error_message
            from .keyboards.menus import keyboards
            
            # Create user-friendly error message
            if "timeout" in str(error).lower():
                error_msg = format_error_message(
                    "Request Timeout",
                    "The request took too long to complete. Please try again."
                )
            elif "connection" in str(error).lower():
                error_msg = format_error_message(
                    "Connection Error",
                    "Unable to connect to services. Please check your connection and try again."
                )
            elif "forbidden" in str(error).lower() or "unauthorized" in str(error).lower():
                error_msg = format_error_message(
                    "Access Error",
                    "Authentication failed. Please restart the bot with /start."
                )
            else:
                error_msg = format_error_message(
                    "Something Went Wrong",
                    "An unexpected error occurred. Please try again later."
                )
            
            try:
                await update.effective_message.reply_text(
                    error_msg,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboards.error_menu()
                )
            except Exception as e:
                logger.error(f"Error while sending error message: {e}")

async def post_init(application: Application):
    """Initialize bot data after application starts."""
    application.bot_data["api_url"] = API_URL
    application.bot_data["api_key"] = BOT_API_KEY
    
    logger.info(f"🤖 Bot initialized with API URL: {API_URL}")
    logger.info(f"🌐 Environment: {ENVIRONMENT}")
    logger.info(f"🔧 Render deployment: {IS_RENDER}")
    
    # Note: Webhook configuration is handled by the backend service
    # in production (Render) mode. This bot instance handles polling mode only.
    if not IS_RENDER:
        logger.info("Running in polling mode - webhook setup handled by backend")

def main():
    """Start the bot."""
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        return

    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

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

    # Add all handlers to the application
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("price", price_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("settings", settings_command))
    application.add_handler(send_conversation_handler)
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    application.add_error_handler(error_handler)

    # Start the bot - always use polling when running this script directly
    # Production webhook mode is handled by the backend service
    logger.info("🏠 Starting bot with polling mode...")
    application.run_polling(
        drop_pending_updates=True,
        allowed_updates=["message", "callback_query", "inline_query"]
    )

if __name__ == "__main__":
    main()
