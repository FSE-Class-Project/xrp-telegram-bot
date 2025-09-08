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
API_URL = os.getenv("API_URL", "http://localhost:8000")
WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL")

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
            await price_command(update, context)

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Log errors and send a user-friendly message using HTML."""
    logger.error(f'Update "{update}" caused error "{context.error}"')

    if isinstance(update, Update) and update.effective_message:
        error_msg = "❌ <b>Something went wrong</b>\n\nPlease try again later."
        try:
            await update.effective_message.reply_text(
                error_msg, parse_mode=ParseMode.HTML
            )
        except Exception as e:
            logger.error(f"Error while sending error message: {e}")

async def post_init(application: Application):
    """Initialize bot data after application starts."""
    application.bot_data["api_url"] = API_URL
    logger.info(f"Bot initialized with API URL: {API_URL}")

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
    application.add_handler(send_conversation_handler)
    application.add_handler(CallbackQueryHandler(callback_query_handler))
    application.add_error_handler(error_handler)

    # Start the bot
    if WEBHOOK_URL:
        logger.info(f"Starting bot with webhook: {WEBHOOK_URL}")
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get("PORT", 8443)),
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}",
        )
    else:
        logger.info("Starting bot with polling...")
        application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
