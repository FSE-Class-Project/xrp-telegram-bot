from telegram import Update, ParseMode
from telegram.ext import ContextTypes
import httpx

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command - Register user"""
    user = update.effective_user
    
    # Send initial message
    await update.message.reply_text(
        "🎉 **Welcome to XRP Ledger Bot!**\n\n"
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
                
                # Send success message with wallet info
                message = (
                    "✅ **Wallet Created Successfully!**\n\n"
                    f"📬 **Your XRP Address:**\n`{data['xrp_address']}`\n\n"
                    f"💰 **Balance:** {data['balance']} XRP\n\n"
                    "⚠️ *This is TestNet XRP for testing only*\n\n"
                    "Use /help to see available commands."
                )
                
                await update.message.reply_text(
                    message,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                # User might already exist, try to get their info
                response = await client.get(
                    f"{context.bot_data['api_url']}/api/v1/wallet/balance/{user.id}",
                    timeout=10.0
                )
                
                if response.status_code == 200:
                    data = response.json()
                    
                    message = (
                        f"👋 **Welcome back, {user.first_name or user.username or 'User'}!**\n\n"
                        f"📬 **Your XRP Address:**\n`{data['address']}`\n\n"
                        f"💰 **Balance:** {data['balance']} XRP\n\n"
                        "Use /help to see available commands."
                    )
                    
                    await update.message.reply_text(
                        message,
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    raise Exception("Failed to register or retrieve user")
                    
    except Exception as e:
        await update.message.reply_text(
            f"❌ **Error**\n\nRegistration failed: {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )

async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command"""
    help_text = """
📚 **Available Commands**

💰 /balance - Check your XRP balance
📤 /send - Send XRP to another address
📊 /price - View current XRP price
📜 /history - View transaction history
👤 /profile - View your profile
❓ /help - Show this message

**How to send XRP:**
Use: `/send [amount] [address]`
Example: `/send 10 rN7n7...`

**Need assistance?** 
Contact support or check the docs.
    """
    
    await update.message.reply_text(
        help_text,
        parse_mode=ParseMode.MARKDOWN
    )