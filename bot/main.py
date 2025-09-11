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

# Configure logging based on environment
log_level = logging.DEBUG if os.getenv("DEBUG", "").lower() == "true" else logging.INFO
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=log_level,
)

# Reduce noisy library logging
if os.getenv("ENVIRONMENT") == "production" or not os.getenv("DEBUG"):
    # Production: Minimal noise
    logging.getLogger("httpx").setLevel(logging.ERROR)
    logging.getLogger("httpcore").setLevel(logging.ERROR)
    logging.getLogger("telegram").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext").setLevel(logging.WARNING)
else:
    # Development: Reduce polling noise but keep important messages
    logging.getLogger("httpx").setLevel(logging.WARNING)
    logging.getLogger("httpcore").setLevel(logging.WARNING)
    logging.getLogger("telegram.ext.ExtBot").setLevel(logging.INFO)  # Hide DEBUG polling messages
    logging.getLogger("telegram.ext.Updater").setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# --- Configuration ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BOT_API_KEY = None  # Will be initialized later
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
            # Handle callback query errors with retry logic
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await update.callback_query.answer(
                        "⚠️ An error occurred. Please try again.", 
                        show_alert=True
                    )
                    break
                except Exception as e:
                    logger.error(f"Failed to answer callback query (attempt {attempt + 1}): {e}")
                    if attempt == max_retries - 1:
                        logger.error("All callback query answer attempts failed")
        
        # Send error message to user with proper error classification
        if update.effective_message:
            try:
                from .utils.formatting import format_error_message
                from .keyboards.menus import keyboards
                
                # Classify and handle different error types
                error_str = str(error).lower()
                
                if "timeout" in error_str or "asyncio.timeouterror" in error_str:
                    error_msg = format_error_message(
                        "Request Timeout",
                        "The request took too long to complete. Please try again."
                    )
                elif "connection" in error_str or "connect" in error_str:
                    error_msg = format_error_message(
                        "Connection Error",
                        "Unable to connect to backend services. Please try again in a moment."
                    )
                elif "forbidden" in error_str or "unauthorized" in error_str:
                    error_msg = format_error_message(
                        "Access Error",
                        "Authentication failed. Please restart the bot with /start."
                    )
                elif "badrequest" in error_str or "bad request" in error_str:
                    error_msg = format_error_message(
                        "Invalid Request",
                        "The request was invalid. Please check your input and try again."
                    )
                elif "network" in error_str or "dns" in error_str:
                    error_msg = format_error_message(
                        "Network Error",
                        "Network connectivity issue. Please check your connection."
                    )
                else:
                    error_msg = format_error_message(
                        "Something Went Wrong",
                        "An unexpected error occurred. Please try again later."
                    )
                
                # Try to send error message with fallback
                try:
                    await update.effective_message.reply_text(
                        error_msg,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboards.error_menu() if 'keyboards' in locals() else None
                    )
                except Exception as send_error:
                    # Fallback: send simple text message
                    logger.error(f"Failed to send formatted error message: {send_error}")
                    try:
                        await update.effective_message.reply_text(
                            "⚠️ An error occurred. Please try again later.",
                            reply_markup=None
                        )
                    except Exception as final_error:
                        logger.error(f"Failed to send fallback error message: {final_error}")
            
            except ImportError as import_error:
                logger.error(f"Import error in error handler: {import_error}")
                # Minimal fallback when imports fail
                try:
                    await update.effective_message.reply_text("⚠️ Service temporarily unavailable. Please try again.")
                except Exception as e:
                    logger.error(f"Final fallback error message failed: {e}")
            except Exception as e:
                logger.error(f"Error in error message handling: {e}")
                # Absolute fallback
                try:
                    await update.effective_message.reply_text("⚠️ Error occurred. Please restart with /start.")
                except:
                    pass  # Nothing more we can do

async def post_init(application: Application):
    """Initialize bot data after application starts."""
    global BOT_API_KEY
    
    # Initialize API key from backend settings
    if not BOT_API_KEY:
        try:
            from backend.config import initialize_settings
            settings = initialize_settings()
            BOT_API_KEY = settings.BOT_API_KEY
            logger.info("✅ API key synchronized with backend settings")
        except Exception as e:
            logger.warning(f"⚠️ Could not get API key from backend settings: {e}")
            BOT_API_KEY = os.getenv("BOT_API_KEY", "dev-bot-fallback-key")
    
    application.bot_data["api_url"] = API_URL
    application.bot_data["api_key"] = BOT_API_KEY
    
    logger.info(f"🤖 Bot initialized with API URL: {API_URL}")
    logger.info(f"🌐 Environment: {ENVIRONMENT}")
    logger.info(f"🔧 Render deployment: {IS_RENDER}")
    
    # Determine execution mode based on environment
    if IS_RENDER or ENVIRONMENT == "production":
        logger.info("Production mode detected - bot should only run via webhook")
        if __name__ == "__main__":
            logger.warning("⚠️ Bot main.py should not be run directly in production!")
            logger.warning("⚠️ Webhooks are handled by the backend service")
    else:
        logger.info("Development mode - using polling")

def main():
    """Start the bot."""
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        return

    # Check if we should be running in production mode
    if IS_RENDER or ENVIRONMENT == "production":
        logger.error("❌ This script should not be run directly in production!")
        logger.error("❌ In production, the bot runs via webhooks through the backend service")
        logger.info("💡 Use the backend service instead: python -m backend.main")
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

    # Start the bot in development polling mode
    logger.info("🏠 Starting bot in development polling mode...")
    try:
        application.run_polling(
            drop_pending_updates=True,
            allowed_updates=["message", "callback_query", "inline_query"]
        )
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Bot error: {e}")
        raise

if __name__ == "__main__":
    main()
