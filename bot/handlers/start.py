from telegram import Update
from telegram.ext import ContextTypes
from telegram.constants import ParseMode
from messages.templates import welcome, help_text, cancel_text, clear_text

DEFAULT_LANG = "en" 

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command"""
    user = update.effective_user
    await update.message.reply_text(
        text=welcome(user.first_name, lang=DEFAULT_LANG),
        parse_mode=ParseMode.MARKDOWN
    )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    await update.message.reply_text(
        text=help_text(lang=DEFAULT_LANG),
        parse_mode=ParseMode.MARKDOWN
    )

async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /cancel command - Stop outgoing transactions"""
    # Clear transaction-related data
    if 'user_data' in context:
        # Remove transaction-specific data
        transaction_keys = ['pending_transaction', 'transaction_amount', 'recipient', 'memo']
        for key in transaction_keys:
            context.user_data.pop(key, None)
    
    # Clear any pending transaction operations
    if 'chat_data' in context:
        context.chat_data.pop('transaction_in_progress', None)
    
    await update.message.reply_text(
        text=cancel_text(lang=DEFAULT_LANG),
        parse_mode=ParseMode.MARKDOWN
    )

async def clear_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /clear command - Clear chat data"""
    # Clear all user data (conversation state)
    if 'user_data' in context:
        context.user_data.clear()
    
    # Clear all chat data (temporary information)
    if 'chat_data' in context:
        context.chat_data.clear()
    
    await update.message.reply_text(
        text=clear_text(lang=DEFAULT_LANG),
        parse_mode=ParseMode.MARKDOWN
    )