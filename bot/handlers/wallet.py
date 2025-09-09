# bot/handlers/wallet.py
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
import httpx
from datetime import datetime
from html import escape

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command using HTML formatting."""
    # Ensure message and user objects exist before proceeding.
    if not update.message or not update.effective_user:
        return
        
    user_id = update.effective_user.id
    
    try:
        async with httpx.AsyncClient() as client:
            api_url = context.bot_data.get('api_url', 'http://localhost:8000')
            
            # Get balance from API
            response = await client.get(f"{api_url}/api/v1/wallet/balance/{user_id}")
            response.raise_for_status() # Raise HTTP errors
            
            balance_data = response.json()
            
            # Get current price for USD value
            price_response = await client.get(f"{api_url}/api/v1/price/current")
            price_data = price_response.json() if price_response.status_code == 200 else {}
            
            balance_xrp = balance_data.get('balance', 0)
            price_usd = price_data.get('price_usd', 0)
            usd_value = balance_xrp * price_usd
            
            # Format message with HTML
            message = (
                f"💰 <b>Your Balance</b>\n\n"
                f"📬 <b>Address:</b> <code>{escape(balance_data.get('address', 'N/A'))}</code>\n"
                f"💵 <b>Balance:</b> {balance_xrp:.6f} XRP\n"
                f"📈 <b>USD Value:</b> ${usd_value:,.2f}\n\n"
                f"<i>Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
            )
            
            # The reply_markup would come from your keyboards file.
            # If `keyboards` is a valid object, this will work at runtime.
            # reply_markup = keyboards.wallet_menu() 
            await update.message.reply_text(message, parse_mode=ParseMode.HTML) #, reply_markup=reply_markup)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            error_msg = "❌ <b>Not Registered</b>\n\nYou need to register first!\nUse /start to create your wallet."
        else:
            error_msg = f"A server error occurred: {e.response.status_code}"
        await update.message.reply_text(error_msg, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        error_msg = f"❌ <b>Error</b>\n\nCould not retrieve balance: <code>{escape(str(e))}</code>"
        await update.message.reply_text(error_msg, parse_mode=ParseMode.HTML)


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /profile command using HTML formatting."""
    if not update.message or not update.effective_user:
        return

    user = update.effective_user
    
    try:
        async with httpx.AsyncClient() as client:
            api_url = context.bot_data.get('api_url', 'http://localhost:8000')

            # Get user wallet data
            response = await client.get(f"{api_url}/api/v1/wallet/balance/{user.id}")
            response.raise_for_status()
            wallet_data = response.json()
            
            # Get transaction count
            tx_response = await client.get(f"{api_url}/api/v1/transaction/history/{user.id}")
            tx_count = len(tx_response.json().get('transactions', [])) if tx_response.status_code == 200 else 0
            
            username = f"@{escape(user.username)}" if user.username else "Not set"
            
            # Format message with HTML
            message = (
                f"👤 <b>Your Profile</b>\n\n"
                f"<b>Telegram ID:</b> <code>{user.id}</code>\n"
                f"<b>Username:</b> {username}\n\n"
                f"<b>XRP Wallet:</b>\n"
                f"  📬 <b>Address:</b> <code>{escape(wallet_data.get('address', 'N/A'))}</code>\n"
                f"  💰 <b>Balance:</b> {wallet_data.get('balance', 0):.6f} XRP\n"
                f"  📊 <b>Total Transactions:</b> {tx_count}\n\n"
                "Use /settings to manage preferences."
            )
            
            await update.message.reply_text(message, parse_mode=ParseMode.HTML)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            error_msg = "❌ <b>Not Registered</b>\n\nYou need to register first!\nUse /start to create your wallet."
        else:
            error_msg = f"A server error occurred: {e.response.status_code}"
        await update.message.reply_text(error_msg, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        error_msg = f"❌ <b>Error</b>\n\nCould not retrieve profile: <code>{escape(str(e))}</code>"
        await update.message.reply_text(error_msg, parse_mode=ParseMode.HTML)
