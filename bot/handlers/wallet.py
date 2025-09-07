# bot/handlers/wallet.py
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
            
            data = response.json()
            
            if data.get("success"):
                # Get current price for USD value
                price_response = await client.get(
                    f"{context.bot_data['api_url']}/api/v1/price/current",
                    timeout=10.0
                )
                
                price_data = price_response.json() if price_response.status_code == 200 else {"price_usd": 0}
                usd_value = data['balance'] * price_data.get('price_usd', 0)
                
                message = (
                    "💰 *Your Balance*\n\n"
                    f"📬 *Address:* `{data['address']}`\n"
                    f"💵 *Balance:* {data['balance']:.6f} XRP\n"
                    f"💲 *USD Value:* ${usd_value:.2f}\n\n"
                    f"_Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}_"
                )
                
                await update.message.reply_text(
                    message,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                error = data.get("error", "Unknown error")
                if "not found" in error.lower():
                    await update.message.reply_text(
                        "❌ *Not Registered*\n\n"
                        "You need to register first!\n"
                        "Use /start to create your wallet.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                else:
                    await update.message.reply_text(
                        f"❌ *Error*\n\n{error}",
                        parse_mode=ParseMode.MARKDOWN
                    )
                
    except Exception as e:
        await update.message.reply_text(
            f"❌ *Error*\n\nCould not retrieve balance: {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )

async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /profile command"""
    user = update.effective_user
    
    try:
        async with httpx.AsyncClient() as client:
            # Get user data
            response = await client.get(
                f"{context.bot_data['api_url']}/api/v1/user/{user.id}",
                timeout=10.0
            )
            
            data = response.json()
            
            if data.get("success"):
                created_date = datetime.fromisoformat(data['created_at']).strftime('%Y-%m-%d')
                
                message = (
                    "👤 *Your Profile*\n\n"
                    f"*Telegram ID:* {data['telegram_id']}\n"
                    f"*Username:* @{data.get('telegram_username') or 'Not set'}\n"
                    f"*Registered:* {created_date}\n\n"
                    "*XRP Wallet:*\n"
                    f"📬 Address: `{data['xrp_address']}`\n"
                    f"💰 Balance: {data['balance']:.6f} XRP\n"
                    f"📊 Total Transactions: {data['transaction_count']}\n\n"
                    "Use /settings to manage preferences."
                )
                
                await update.message.reply_text(
                    message,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    "❌ *Not Registered*\n\n"
                    "You need to register first!\n"
                    "Use /start to create your wallet.",
                    parse_mode=ParseMode.MARKDOWN
                )
                
    except Exception as e:
        await update.message.reply_text(
            f"❌ *Error*\n\nCould not retrieve profile: {str(e)}",
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
            
            data = response.json()
            
            if data.get("success"):
                transactions = data.get('transactions', [])
                
                if not transactions:
                    await update.message.reply_text(
                        "📜 *Transaction History*\n\n"
                        "No transactions found.",
                        parse_mode=ParseMode.MARKDOWN
                    )
                    return
                
                # Format transaction history
                history_text = "📜 *Transaction History*\n\n"
                
                for tx in transactions[:10]:
                    status_emoji = "✅" if tx['status'] == 'confirmed' else "❌"
                    type_emoji = "📤" if tx['type'] == 'sent' else "📥"
                    
                    history_text += f"{type_emoji} {status_emoji} *{tx['amount']:.2f} XRP*\n"
                    
                    if tx['type'] == 'sent':
                        history_text += f"To: `{tx['address'][:10]}...`\n"
                    else:
                        history_text += f"From: `{tx['address'][:10]}...`\n"
                    
                    history_text += f"Status: {tx['status']}\n"
                    
                    # Parse and format timestamp
                    tx_time = datetime.fromisoformat(tx['timestamp']).strftime('%Y-%m-%d %H:%M')
                    history_text += f"Date: {tx_time}\n"
                    
                    if tx.get('hash'):
                        history_text += f"Hash: `{tx['hash'][:10]}...`\n"
                    
                    history_text += "\n"
                
                await update.message.reply_text(
                    history_text,
                    parse_mode=ParseMode.MARKDOWN
                )
            else:
                await update.message.reply_text(
                    "❌ *Error*\n\n" + data.get("error", "Could not retrieve history"),
                    parse_mode=ParseMode.MARKDOWN
                )
                
    except Exception as e:
        await update.message.reply_text(
            f"❌ *Error*\n\nCould not retrieve history: {str(e)}",
            parse_mode=ParseMode.MARKDOWN
        )

