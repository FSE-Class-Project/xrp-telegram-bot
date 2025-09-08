# bot/handlers/start.py
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
import httpx
from html import escape

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - Register user and create/fetch wallet info."""
    user = update.effective_user
    # Ensure the message and user objects exist before proceeding.
    # This resolves the Pylance "OptionalMemberAccess" error.
    if not update.message or not user:
        return

    # Send initial message while the backend processes the request
    await update.message.reply_text(
        "🎉 <b>Welcome to the XRP Ledger Bot!</b>\n\n"
        "I'm setting up your wallet, please wait a moment... ⏳",
        # Use HTML parse mode for more reliable formatting
        parse_mode=ParseMode.HTML
    )
    
    # Prepare user data for the backend API
    user_data = {
        "telegram_id": str(user.id),
        "telegram_username": user.username,
        "telegram_first_name": user.first_name,
        "telegram_last_name": user.last_name
    }
    
    try:
        # Call backend API to register the user and get wallet details
        async with httpx.AsyncClient() as client:
            # Ensure the api_url is correctly passed in your bot's main setup
            api_url = context.bot_data.get('api_url', 'http://localhost:8000')
            response = await client.post(
                f"{api_url}/api/v1/user/register",
                json=user_data,
                timeout=30.0
            )
        
        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)
        
        data = response.json()
        
        # We escape the user's name to prevent any potential HTML formatting issues
        safe_first_name = escape(user.first_name or 'User')
        
        if data.get("is_new"):
            # Message for a newly registered user
            message = (
                "✅ <b>Wallet Created Successfully!</b>\n\n"
                f"📬 <b>Your XRP Address:</b>\n<code>{escape(data['xrp_address'])}</code>\n\n"
                f"💰 <b>Initial Balance:</b> {data['balance']:.2f} XRP\n\n"
                "⚠️ <i>This is a TestNet wallet with TestNet XRP for testing only.</i>\n\n"
                "Type /help to see all available commands."
            )
        else:
            # Message for a returning user
            message = (
                f"👋 <b>Welcome back, {safe_first_name}!</b>\n\n"
                f"📬 <b>Your XRP Address:</b>\n<code>{escape(data['xrp_address'])}</code>\n\n"
                f"💰 <b>Current Balance:</b> {data['balance']:.2f} XRP\n\n"
                "What would you like to do today?\n"
                "Type /help to see all available commands."
            )
            
        await update.message.reply_text(message, parse_mode=ParseMode.HTML)
            
    except httpx.HTTPStatusError as e:
        # Handle specific HTTP errors from the backend
        error_message = f"Failed to communicate with the backend: Server responded with {e.response.status_code}."
        await update.message.reply_text(
            f"❌ <b>Error</b>\n\nCould not set up your wallet.\n<b>Reason:</b> <code>{escape(error_message)}</code>",
            parse_mode=ParseMode.HTML
        )
    except Exception as e:
        # Handle other errors like network issues or timeouts
        await update.message.reply_text(
            f"❌ <b>An Unexpected Error Occurred</b>\n\nRegistration failed. Please try again later.\n"
            f"<b>Details:</b> <code>{escape(str(e))}</code>",
            parse_mode=ParseMode.HTML
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command and display available commands."""
    # Ensure the message object exists before proceeding.
    if not update.message:
        return

    help_text = """
📚 <b>Available Commands</b>

💰 /balance - Check your XRP balance
📤 /send - Send XRP to another address
📊 /price - View current XRP price
📜 /history - View transaction history
👤 /profile - View your profile
⚙️ /settings - Manage preferences
❓ /help - Show this message

<b>How to send XRP:</b>
Use: <code>/send [amount] [address]</code>
Example: <code>/send 10 rN7n7...</code>

Or just type /send and follow the prompts!

<i>Need assistance?</i> 
Visit the <a href="https://xrpl.org">XRP Ledger Docs</a>.
    """
    
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True
    )

