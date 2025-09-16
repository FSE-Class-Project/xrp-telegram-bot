import logging
import os

from dotenv import load_dotenv
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

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
    logging.getLogger("telegram.ext.ExtBot").setLevel(logging.INFO)
    logging.getLogger("telegram.ext.Updater").setLevel(logging.INFO)

logger = logging.getLogger(__name__)

# --- Configuration ---
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
BOT_API_KEY = None  # Will be initialized later
API_URL = os.getenv("API_URL", "http://localhost:8000")
WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL")
RENDER_URL = os.getenv("RENDER_EXTERNAL_URL")
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
    send_mode_handler,
    beneficiary_selection_handler,
    beneficiary_add_alias_handler,
    beneficiary_add_address_handler,
    amount_handler,
    address_handler,
    confirm_handler,
    cancel_handler,
    history_command, # This is now defined in transaction.py
    MODE,
    BENEFICIARY_SELECT,
    BENEFICIARY_ADD_ALIAS,
    BENEFICIARY_ADD_ADDRESS,
    AMOUNT,
    ADDRESS,
    CONFIRM,
)
from .handlers.price import price_command
from .handlers.settings import settings_command
from .keyboards.menus import keyboards # Import the keyboards object


async def callback_query_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle all inline keyboard button presses."""
    query = update.callback_query
    if not query or not query.data:
        return

    # Answer the callback to remove the "loading" state from the button
    await query.answer()

    # --- Navigation stack management ---
    user_data = context.user_data
    nav_stack = user_data.setdefault("nav_stack", [])
    current_menu = user_data.get("current_menu", "main_menu")

    data = query.data

    # Helper to route to a given menu id
    async def route_to(menu_id: str):
        user_data["current_menu"] = menu_id
        if menu_id == "main_menu":
            message = "🏠 <b>Main Menu</b>\n\nWhat would you like to do?"
            if query.message:
                await query.message.edit_text(
                    message,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboards.main_menu(),
                )
            return
        # Map menu id to handler
        if menu_id == "balance":
            await balance_command(update, context)
        elif menu_id == "send" or menu_id == "send_xrp":
            await send_command(update, context)
        elif menu_id == "price":
            await price_command(update, context)
        elif menu_id == "history":
            try:
                from .handlers.history import history_command as hist_cmd

                await hist_cmd(update, context)
            except Exception:
                await history_command(update, context)
        elif menu_id == "profile":
            await profile_command(update, context)
        elif menu_id == "help":
            await help_command(update, context)
        elif menu_id == "settings":
            await settings_command(update, context)
        elif menu_id == "market_stats":
            from .handlers.price import market_stats_callback

            await market_stats_callback(update, context)
        elif menu_id in (
            "notification_settings",
            "currency_settings",
            "security_settings",
            "language_settings",
            "export_data",
            "delete_account",
        ):
            from .handlers.settings import (
                currency_settings,
                delete_account_warning,
                export_data,
                language_settings,
                notification_settings,
                security_settings,
            )

            if menu_id == "notification_settings":
                await notification_settings(update, context)
            elif menu_id == "currency_settings":
                await currency_settings(update, context)
            elif menu_id == "security_settings":
                await security_settings(update, context)
            elif menu_id == "language_settings":
                await language_settings(update, context)
            elif menu_id == "export_data":
                await export_data(update, context)
            elif menu_id == "delete_account":
                await delete_account_warning(update, context)
        else:
            await route_to("main_menu")
            return

    # Handle universal back
    if data == "back":
        target = nav_stack.pop() if nav_stack else "main_menu"
        await route_to(target)
        return

    # Determine if this is an in-place action
    is_refresh = (
        data.startswith("refresh_") or data.startswith("history_page_") or data in ("page_info",)
    )

    # Before navigating forward, push current menu onto stack
    def push_if_forward(target_id: str):
        if not is_refresh and target_id and target_id != current_menu:
            if current_menu and current_menu != "main_menu":
                nav_stack.append(current_menu)

    # Route based on callback data
    if data == "balance":
        push_if_forward("balance")
        await balance_command(update, context)
        user_data["current_menu"] = "balance"
    elif data in ("send", "send_xrp"):
        push_if_forward("send")
        await send_command(update, context)
        user_data["current_menu"] = "send"
    elif data == "price":
        push_if_forward("price")
        await price_command(update, context)
        user_data["current_menu"] = "price"
    elif data == "history":
        push_if_forward("history")
        try:
            from .handlers.history import history_command as hist_cmd

            await hist_cmd(update, context)
        except Exception:
            await history_command(update, context)
        user_data["current_menu"] = "history"
    elif data == "profile":
        push_if_forward("profile")
        await profile_command(update, context)
        user_data["current_menu"] = "profile"
    elif data == "help":
        push_if_forward("help")
        await help_command(update, context)
        user_data["current_menu"] = "help"
    elif data == "main_menu":
        nav_stack.clear()
        message = "🏠 <b>Main Menu</b>\n\nWhat would you like to do?"
        if query.message:
            await query.message.edit_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboards.main_menu(),
            )
        user_data["current_menu"] = "main_menu"
    elif query.data.startswith("refresh_"):
        if data == "refresh_balance":
            await balance_command(update, context)
        elif data == "refresh_price":
            from .handlers.price import price_refresh_callback

            await price_refresh_callback(update, context)
        elif data == "refresh_history":
            await history_command(update, context)
    elif data.startswith("history_page_"):
        try:
            from .handlers.history import history_page

            await history_page(update, context)
        except Exception:
            await history_command(update, context)
        user_data["current_menu"] = "history"
    elif data == "market_stats":
        push_if_forward("market_stats")
        from .handlers.price import market_stats_callback

        await market_stats_callback(update, context)
        user_data["current_menu"] = "market_stats"
    elif data.startswith(
        (
            "notification_",
            "currency_",
            "security_",
            "language_",
            "export_",
            "delete_",
            "toggle_",
            "set_",
            "setup_",
        )
    ):
        from .handlers.settings import (
            currency_settings,
            delete_account_warning,
            export_data,
            language_settings,
            notification_settings,
            security_settings,
            set_currency,
            toggle_setting,
        )

        if data == "notification_settings":
            push_if_forward("notification_settings")
            await notification_settings(update, context)
            user_data["current_menu"] = "notification_settings"
        elif data == "currency_settings":
            push_if_forward("currency_settings")
            await currency_settings(update, context)
            user_data["current_menu"] = "currency_settings"
        elif data == "security_settings":
            push_if_forward("security_settings")
            await security_settings(update, context)
            user_data["current_menu"] = "security_settings"
        elif data == "language_settings":
            push_if_forward("language_settings")
            await language_settings(update, context)
            user_data["current_menu"] = "language_settings"
        elif data == "export_data":
            push_if_forward("export_data")
            await export_data(update, context)
            user_data["current_menu"] = "export_data"
        elif data == "delete_account":
            push_if_forward("delete_account")
            await delete_account_warning(update, context)
            user_data["current_menu"] = "delete_account"
        elif data.startswith("toggle_"):
            setting_name = data[7:]
            await toggle_setting(update, context, setting_name)
        elif data.startswith("set_currency_"):
            currency = data[13:]
            await set_currency(update, context, currency)
    elif data == "settings":
        push_if_forward("settings")
        await settings_command(update, context)
        user_data["current_menu"] = "settings"
    elif data in ["retry", "cancel_send", "confirm_send"]:
        if data == "retry":
            await query.message.edit_text(
                "🔄 <b>Retry</b>\n\nPlease try your last action again.",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboards.main_menu(),
            )
        elif data == "cancel_send":
            await query.message.edit_text(
                "❌ <b>Transaction Cancelled</b>\n\nTransaction has been cancelled.",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboards.main_menu(),
            )
        elif data == "confirm_send":
            logger.info("Transaction confirmation requested")
            await query.message.edit_text(
                "✅ <b>Transaction Confirmed</b>\n\nProcessing your transaction...",
                parse_mode=ParseMode.HTML,
                reply_markup=keyboards.main_menu(),
            )


async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Enhanced error handler with detailed logging and user-friendly messages."""
    error = context.error
    logger.error(f'Update "{update}" caused error "{error}"', exc_info=error)

    if isinstance(update, Update):
        if update.callback_query:
            max_retries = 3
            for attempt in range(max_retries):
                try:
                    await update.callback_query.answer(
                        "⚠️ An error occurred. Please try again.", show_alert=True
                    )
                    break
                except Exception as e:
                    logger.error(f"Failed to answer callback query (attempt {attempt + 1}): {e}")
                    if attempt == max_retries - 1:
                        logger.error("All callback query answer attempts failed")

        if update.effective_message:
            try:
                from .keyboards.menus import keyboards
                from .utils.formatting import format_error_message

                error_str = str(error).lower()

                if "timeout" in error_str or "asyncio.timeouterror" in error_str:
                    error_msg = format_error_message(
                        "Request Timeout",
                        "The request took too long to complete. Please try again.",
                    )
                elif "connection" in error_str or "connect" in error_str:
                    error_msg = format_error_message(
                        "Connection Error",
                        "Unable to connect to backend services. Please try again in a moment.",
                    )
                elif "forbidden" in error_str or "unauthorized" in error_str:
                    error_msg = format_error_message(
                        "Access Error", "Authentication failed. Please restart the bot with /start."
                    )
                elif "badrequest" in error_str or "bad request" in error_str:
                    error_msg = format_error_message(
                        "Invalid Request",
                        "The request was invalid. Please check your input and try again.",
                    )
                elif "network" in error_str or "dns" in error_str:
                    error_msg = format_error_message(
                        "Network Error", "Network connectivity issue. Please check your connection."
                    )
                else:
                    error_msg = format_error_message(
                        "Something Went Wrong",
                        "An unexpected error occurred. Please try again later.",
                    )

                try:
                    await update.effective_message.reply_text(
                        error_msg,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboards.error_menu() if "keyboards" in locals() else None,
                    )
                except Exception as send_error:
                    logger.error(f"Failed to send formatted error message: {send_error}")
                    try:
                        await update.effective_message.reply_text(
                            "⚠️ An error occurred. Please try again later.", reply_markup=None
                        )
                    except Exception as final_error:
                        logger.error(f"Failed to send fallback error message: {final_error}")

            except ImportError as import_error:
                logger.error(f"Import error in error handler: {import_error}")
                try:
                    await update.effective_message.reply_text(
                        "⚠️ Service temporarily unavailable. Please try again."
                    )
                except Exception as e:
                    logger.error(f"Final fallback error message failed: {e}")
            except Exception as e:
                logger.error(f"Error in error message handling: {e}")
                try:
                    await update.effective_message.reply_text(
                        "⚠️ Error occurred. Please restart with /start."
                    )
                except Exception:
                    pass


async def post_init(application: Application):
    """Initialize bot data after application starts."""
    global BOT_API_KEY

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

    if IS_RENDER or ENVIRONMENT == "production":
        logger.info("Production mode detected - bot should only run via webhook")
        if __name__ == "__main__":
            logger.warning("⚠️ Bot main.py should not be run directly in production!")
            logger.warning("⚠️ Webhooks are handled by the backend service")
    else:
        logger.info("Development mode - using polling")


def setup_handlers(application: Application):
    """Setup all bot handlers - can be called from backend for webhook mode."""

    # Create conversation handler for send command
    send_conversation_handler = ConversationHandler(
        entry_points=[
            CommandHandler("send", send_command),
            CallbackQueryHandler(send_command, pattern=r"^(send|send_xrp)$"),
        ],
        states={
            MODE: [
                CallbackQueryHandler(send_mode_handler, pattern=r"^send_mode_(beneficiary|address)$"),
                CallbackQueryHandler(cancel_handler, pattern=r"^cancel_send$"),
            ],
            BENEFICIARY_SELECT: [
                CallbackQueryHandler(beneficiary_selection_handler, pattern=r"^beneficiary_(select:.*|add)$"),
                CallbackQueryHandler(cancel_handler, pattern=r"^cancel_send$"),
            ],
            BENEFICIARY_ADD_ALIAS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, beneficiary_add_alias_handler),
                CallbackQueryHandler(cancel_handler, pattern=r"^cancel_send$"),
            ],
            BENEFICIARY_ADD_ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, beneficiary_add_address_handler),
                CallbackQueryHandler(cancel_handler, pattern=r"^cancel_send$"),
            ],
            AMOUNT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, amount_handler),
                CallbackQueryHandler(cancel_handler, pattern=r"^cancel_send$"),
            ],
            ADDRESS: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, address_handler),
                CallbackQueryHandler(cancel_handler, pattern=r"^cancel_send$"),
            ],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_handler)],
        },
        fallbacks=[
            CommandHandler("cancel", cancel_handler),
            CallbackQueryHandler(cancel_handler, pattern=r"^cancel_send$"),
        ],
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

    logger.info("✅ Bot handlers configured successfully")


def main():
    """Start the bot."""
    if not BOT_TOKEN:
        logger.error("TELEGRAM_BOT_TOKEN not found in environment variables!")
        return

    if IS_RENDER or ENVIRONMENT == "production":
        logger.error("❌ This script should not be run directly in production!")
        logger.error("❌ In production, the bot runs via webhooks through the backend service")
        logger.info("💡 Use the backend service instead: python -m backend.main")
        return

    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Setup handlers
    setup_handlers(application)

    logger.info("🏠 Starting bot in development polling mode...")
    try:
        application.run_polling(
            drop_pending_updates=True, allowed_updates=["message", "callback_query", "inline_query"]
        )
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"❌ Bot error: {e}")
        raise


if __name__ == "__main__":
    main()
