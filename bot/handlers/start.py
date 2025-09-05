from telegram import Update
from telegram.ext import ContextTypes

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    await update.message.reply_text("Welcome to XRP Telegram Bot!")

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
Available commands:
/start - Initialize bot
/help - Show this message
/balance - Check your XRP balance
/send - Send XRP to another address
    """
    await update.message.reply_text(help_text)
