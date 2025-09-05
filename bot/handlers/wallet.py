# Handler for wallet commands
from telegram import Update, ParseMode
from telegram.ext import ContextTypes
import httpx
from datetime import datetime

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command"""
    user_id = update.effective_user.id
    
    try:
        async with httpx.AsyncClient() as client:
            # Get balance from API
            response = await client.get(
                f"{context.bot_data['api_url']}/api/v1/wallet/balance/{user_id}",
                timeout=10.0
            )
            
            if response.status_code == 200:
                balance_data = response.json()
                
                # Get current price for USD value
                price_response = await client.get(
                    f"{context.bot_data['api_url']}/api/v1/price/current",
                    timeout=10.0
                )
                
                price_data = price_response.json() if price_response.status_code == 200 else {"price_usd": 0}
                
                usd_value = balance_data['balance'] * price_data.get('price_usd', 0)
                
                message = (
                    "💰 **Your Balance**\n\n"
                    f"📬 **Address:** `{balance_data['address']}`\n"
                    f"💵 **Balance:** {balance_data['balance']:.6f} XRP\n"
                    f"📈 **USD Value:** ${usd_value:.2f}\n\n"
                    f"Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}"
                )
                
                await update.message.reply_text(
                    message,
                    parse_mode=ParseMode.MARKDOWN
                )
            elif response.status_code == 404:
                await update.message.reply_text(
                    "❌ **Not Registered**\n\n"
                    "You need to register first!\n"
                    "Use /start to create your wallet.",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                raise Exception("Failed to get balance")
                
    except Exception as e:
        await update.message.reply_text(
            f"❌ **Error**\n\nCould not retrieve balance: {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /profile command"""
    user = update.effective_user
    
    try:
        async with httpx.AsyncClient() as client:
            # Get user data
            response = await client.get(
                f"{context.bot_data['api_url']}/api/v1/wallet/balance/{user.id}",
                timeout=10.0
            )
            
            if response.status_code == 200:
                wallet_data = response.json()
                
                # Get transaction count
                tx_response = await client.get(
                    f"{context.bot_data['api_url']}/api/v1/transaction/history/{user.id}",
                    timeout=10.0
                )
                
                tx_count = len(tx_response.json().get('transactions', [])) if tx_response.status_code == 200 else 0
                
                message = (
                    "👤 **Your Profile**\n\n"
                    f"**Telegram ID:** {user.id}\n"
                    f"**Username:** @{user.username or 'Not set'}\n"
                    f"**Name:** {user.first_name or ''} {user.last_name or ''}\n\n"
                    "**XRP Wallet:**\n"
                    f"📬 Address: `{wallet_data['address']}`\n"
                    f"💰 Balance: {wallet_data['balance']:.6f} XRP\n"
                    f"📊 Total Transactions: {tx_count}"
                )
                
                await update.message.reply_text(
                    message,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    "❌ **Not Registered**\n\n"
                    "You need to register first!\n"
                    "Use /start to create your wallet.",
                    parse_mode=ParseMode.MARKDOWN
                )
                
    except Exception as e:
        await update.message.reply_text(
            f"❌ **Error**\n\nCould not retrieve profile: {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )

async def history_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /history command"""
    user_id = update.effective_user.id
    
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{context.bot_data['api_url']}/api/v1/transaction/history/{user_id}",
                params={"limit": 10},
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                transactions = data.get('transactions', [])
                
                if not transactions:
                    await update.message.reply_text(
                        "📜 **Transaction History**\n\n"
                        "No transactions found.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
                
                # Format transaction history
                history_text = "📜 **Transaction History**\n\n"
                
                for tx in transactions[:10]:
                    status_emoji = "✅" if tx['status'] == 'confirmed' else "❌"
                    history_text += f"{status_emoji} **{tx['amount']:.6f} XRP**\n"
                    history_text += f"To: `{tx['recipient'][:10]}...`\n"
                    history_text += f"Status: {tx['status']}\n"
                    if tx.get('timestamp'):
                        history_text += f"Date: {tx['timestamp']}\n"
                    if tx.get('hash'):
                        history_text += f"Hash: `{tx['hash'][:10]}...`\n"
                    history_text += "\n"
                
                await update.message.reply_text(
                    history_text,
                    parse_mode=ParseMode.MARKDOWN
                )
                
            elif response.status_code == 404:
                await update.message.reply_text(
                    "❌ **Not Registered**\n\n"
                    "You need to register first!\n"
                    "Use /start to create your wallet.",
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                raise Exception("Failed to get history")
                
    except Exception as e:
        await update.message.reply_text(
            f"❌ **Error**\n\nCould not retrieve history: {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )