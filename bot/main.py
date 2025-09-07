import os
import sys
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    ConversationHandler,
    MessageHandler,
    filters
)
from dotenv import load_dotenv

# Add parent directory to path to import backend modules
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import handlers
from handlers.start import start_command, help_command
from handlers.wallet import balance_command, profile_command, history_command
from handlers.transaction import (
    send_command,
    amount_handler,
    address_handler,
    confirm_handler,
    cancel_handler,
    AMOUNT,
    ADDRESS,
    CONFIRM
)
from handlers.price import price_command

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = os.getenv("API_URL", "http://localhost:8000")
WEBHOOK_URL = os.getenv("TELEGRAM_WEBHOOK_URL")

# Import backend config to get dynamic API URL
try:
    from backend.config import settings
    API_URL = settings.api_url
    logger.info(f"Using API URL from settings: {API_URL}")
except ImportError:
    logger.warning("Could not import backend settings, using environment variable")

async def error_handler(update: Update, context):
    """Log errors and notify user"""
    logger.warning(f'Update "{update}" caused error "{context.error}"')
    
    # Notify user of error
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred while processing your request. Please try again later."
        )

async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /settings command"""
    await update.message.reply_text(
        "⚙️ *Settings*\n\n"
        "Settings management coming soon!\n\n"
        "Available options will include:\n"
        "• Price alerts\n"
        "• Transaction notifications\n"
        "• Display currency\n"
        "• Language preferences",
        parse_mode="Markdown"
    )

async def post_init(application):
    """Initialize bot after startup"""
    # Store API URL in bot data
    application.bot_data['api_url'] = API_URL
    logger.info(f"🤖 Bot initialized with API URL: {API_URL}")
    
    # Test API connection
    try:
        import httpx
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{API_URL}/api/v1/health", timeout=5.0)
            if response.status_code == 200:
                data = response.json()
                logger.info(f"✅ API connection successful: {data}")
            else:
                logger.warning(f"⚠️ API returned status {response.status_code}")
    except Exception as e:
        logger.error(f"❌ Could not connect to API: {e}")

def main():
    """Start the bot"""
    
    if not BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not found in environment variables!")
        logger.error("Please add it to your .env file")
        return
    
    logger.info("🚀 Starting XRP Telegram Bot...")
    logger.info(f"📡 Configured to use API at: {API_URL}")
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("price", price_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("settings", settings_command))
    
    # Add conversation handler for send transaction
    send_conversation_handler = ConversationHandler(
        entry_points=[CommandHandler("send", send_command)],
        states={
            AMOUNT: [MessageHandler(filters.TEXT & ~filters.COMMAND, amount_handler)],
            ADDRESS: [MessageHandler(filters.TEXT & ~filters.COMMAND, address_handler)],
            CONFIRM: [MessageHandler(filters.TEXT & ~filters.COMMAND, confirm_handler)]
        },
        fallbacks=[CommandHandler("cancel", cancel_handler)]
    )
    application.add_handler(send_conversation_handler)
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start bot
    if WEBHOOK_URL:
        # Use webhooks in production
        logger.info(f"🌐 Starting bot with webhook: {WEBHOOK_URL}")
        
        # Parse webhook URL to get the base URL
        webhook_path = BOT_TOKEN
        
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get('PORT', 8443)),
            url_path=webhook_path,
            webhook_url=f"{WEBHOOK_URL}/{webhook_path}",
            drop_pending_updates=True
        )
    else:
        # Use polling for development
        logger.info("🔄 Starting bot with polling...")
        logger.info("✅ Bot is running! Press Ctrl+C to stop.")
        application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()