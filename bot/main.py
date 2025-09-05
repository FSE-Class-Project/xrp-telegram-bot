import os
import logging
from telegram import Update
from telegram.ext import Application, CommandHandler
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

# Configure logging
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO
)
logger = logging.getLogger(__name__)

# Configuration
BOT_TOKEN = os.getenv("TELEGRAM_BOT_TOKEN")
API_URL = os.getenv("API_URL", "http://localhost:8000")

def main():
    """Start the bot"""
    
    # Create application
    application = Application.builder().token(BOT_TOKEN).build()
    
    # Store API URL in bot data
    application.bot_data["api_url"] = API_URL
    
    # Start bot
    logger.info("Starting bot...")
    application.run_polling(drop_pending_updates=True)

if __name__ == "__main__":
    main()
