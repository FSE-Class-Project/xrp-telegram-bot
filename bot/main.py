import os
import logging
from telegram import Update
from telegram.ext import (
    Application,
    CommandHandler,
    MessageHandler,
    filters
)
from dotenv import load_dotenv

# Import handlers
from handlers.start import start_command, help_command, cancel_command, clear_command
from handlers.wallet import balance_command, profile_command, history_command
from handlers.transaction import send_command
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

async def error_handler(update: Update, context):
    """Log errors"""
    logger.warning(f'Update "{update}" caused error "{context.error}"')
    
    # Notify user of error
    if update and update.effective_message:
        await update.effective_message.reply_text(
            "❌ An error occurred while processing your request. Please try again later."
        )

def main():
    """Start the bot"""
    
    if not BOT_TOKEN:
        logger.error("❌ TELEGRAM_BOT_TOKEN not found in environment variables!")
        logger.error("Please add it to your .env file")
        return
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Store API URL in bot data
    application.bot_data['api_url'] = API_URL
    
    logger.info(f"🤖 Bot configured to use API at: {API_URL}")
    
    # Add command handlers
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("balance", balance_command))
    application.add_handler(CommandHandler("send", send_command))
    application.add_handler(CommandHandler("price", price_command))
    application.add_handler(CommandHandler("profile", profile_command))
    application.add_handler(CommandHandler("history", history_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("clear", clear_command))
    
    # Add error handler
    application.add_error_handler(error_handler)
    
    # Start bot
    if WEBHOOK_URL:
        # Use webhooks in production
        logger.info(f"🌐 Starting bot with webhook: {WEBHOOK_URL}")
        application.run_webhook(
            listen="0.0.0.0",
            port=int(os.environ.get('PORT', 8443)),
            url_path=BOT_TOKEN,
            webhook_url=f"{WEBHOOK_URL}/{BOT_TOKEN}"
        )
    else:
        # Use polling for development
        logger.info("🔄 Starting bot with polling...")
        logger.info("✅ Bot is running! Press Ctrl+C to stop.")
        application.run_polling(drop_pending_updates=True)

if __name__ == '__main__':
    main()