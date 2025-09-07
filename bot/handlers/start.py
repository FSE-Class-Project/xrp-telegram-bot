# bot/handlers/start.py
from telegram import Update, ParseMode
from telegram.ext import ContextTypes
import httpx

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - Register user"""
    user = update.effective_user
    
    # Send initial message
    await update.message.reply_text(
        "🎉 *Welcome to XRP Ledger Bot!*\n\n"
        "I'm setting up your wallet... ⏳",
        parse_mode=ParseMode.MARKDOWN
    )
    
    # Prepare user data
    user_data = {
        "telegram_id": str(user.id),
        "telegram_username": user.username,
        "telegram_first_name": user.first_name,
        "telegram_last_name": user.last_name
    }
    
    try:
        # Call backend API to register user
        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{context.bot_data['api_url']}/api/v1/user/register",
                json=user_data,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                if data.get("is_new"):
                    # New user registered
                    message = (
                        "✅ *Wallet Created Successfully!*\n\n"
                        f"📬 *Your XRP Address:*\n`{data['xrp_address']}`\n\n"
                        f"💰 *Initial Balance:* {data['balance']:.2f} XRP\n\n"
                        "⚠️ _This is TestNet XRP for testing only_\n\n"
                        "Use /help to see available commands."
                    )
                else:
                    # Existing user
                    message = (
                        f"👋 *Welcome back, {user.first_name or 'User'}!*\n\n"
                        f"📬 *Your XRP Address:*\n`{data['xrp_address']}`\n\n"
                        f"💰 *Current Balance:* {data['balance']:.2f} XRP\n\n"
                        "What would you like to do today?\n"
                        "Use /help to see available commands."
                    )
                
                await update.message.reply_text(
                    message,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                raise Exception("Failed to register user")
                    
    except Exception as e:
        await update.message.reply_text(
            f"❌ *Error*\n\nRegistration failed: {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
📚 *Available Commands*

💰 /balance - Check your XRP balance
📤 /send - Send XRP to another address
📊 /price - View current XRP price
📜 /history - View transaction history
👤 /profile - View your profile
⚙️ /settings - Manage preferences
❓ /help - Show this message

*How to send XRP:*
Use: `/send [amount] [address]`
Example: `/send 10 rN7n7...`

Or just type /send and follow the prompts!

*Need assistance?* 
Visit [XRP Ledger Docs](https://xrpl.org)
    """
    
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN,
        disable_web_page_preview=True
    )
