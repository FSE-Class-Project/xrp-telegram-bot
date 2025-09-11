# bot/handlers/wallet.py
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
import httpx
from datetime import datetime
import logging

from ..utils.formatting import (
    format_balance_info,
    format_funding_instructions,
    format_error_message,
    format_xrp_address,
    format_username,
    escape_html,
)
from ..keyboards.menus import keyboards

logger = logging.getLogger(__name__)

async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /balance command using HTML formatting."""
    # Handle both message and callback query
    if update.message:
        reply_func = update.message.reply_text
        user_id = update.effective_user.id if update.effective_user else None
    elif update.callback_query:
        reply_func = update.callback_query.message.edit_text
        await update.callback_query.answer()
        user_id = update.callback_query.from_user.id
    else:
        return
    
    if not user_id:
        return
    
    try:
        async with httpx.AsyncClient() as client:
            api_url = context.bot_data.get('api_url', 'http://localhost:8000')
            api_key = context.bot_data.get('api_key', 'dev-bot-api-key-change-in-production')
            
            headers = {"X-API-Key": api_key}
            # Get balance from API
            response = await client.get(f"{api_url}/api/v1/wallet/balance/{user_id}", headers=headers)
            response.raise_for_status() # Raise HTTP errors
            
            balance_data = response.json()
            
            # Get current price for USD value
            price_response = await client.get(f"{api_url}/api/v1/price/current")
            price_data = price_response.json() if price_response.status_code == 200 else {}
            
            balance_xrp = float(balance_data.get('balance', 0))
            available_balance = float(balance_data.get('available_balance', 0))
            price_usd = float(price_data.get('price_usd', 0))
            usd_value = balance_xrp * price_usd
            wallet_address = balance_data.get('address', 'N/A')
            
            # Format message using utility functions
            message = format_balance_info(
                address=wallet_address,
                balance=balance_xrp,
                available=available_balance,
                usd_value=usd_value
            )
            
            # Add funding guidance if needed
            funding_instructions = format_funding_instructions(balance_xrp, is_mainnet=False)
            if funding_instructions:
                message += funding_instructions
            
            # Add inline keyboard for actions
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data="refresh_balance"),
                    InlineKeyboardButton("📤 Send XRP", callback_data="send")
                ],
                [
                    InlineKeyboardButton("📊 Price", callback_data="price"),
                    InlineKeyboardButton("📜 History", callback_data="history")
                ],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ])
            
            await reply_func(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            error_msg = "❌ <b>Not Registered</b>\n\nYou need to register first!\nUse /start to create your wallet."
        else:
            error_msg = f"A server error occurred: {e.response.status_code}"
        await reply_func(error_msg, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        error_msg = format_error_message(f"Could not retrieve balance: {str(e)}")
        await reply_func(error_msg, parse_mode=ParseMode.HTML)


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /profile command using HTML formatting."""
    # Handle both message and callback query
    if update.message:
        reply_func = update.message.reply_text
        user = update.effective_user
    elif update.callback_query:
        reply_func = update.callback_query.message.edit_text
        await update.callback_query.answer()
        user = update.callback_query.from_user
    else:
        return
    
    if not user:
        return
    
    try:
        async with httpx.AsyncClient() as client:
            api_url = context.bot_data.get('api_url', 'http://localhost:8000')
            api_key = context.bot_data.get('api_key', 'dev-bot-api-key-change-in-production')
            
            headers = {"X-API-Key": api_key}
            # Get user wallet data
            response = await client.get(f"{api_url}/api/v1/wallet/balance/{user.id}", headers=headers)
            response.raise_for_status()
            wallet_data = response.json()
            
            # Get transaction count
            tx_response = await client.get(f"{api_url}/api/v1/transaction/history/{user.id}", headers=headers)
            tx_count = len(tx_response.json().get('transactions', [])) if tx_response.status_code == 200 else 0
            
            username = format_username(user.username)
            
            balance_xrp = float(wallet_data.get('balance', 0))
            wallet_address = wallet_data.get('address', 'N/A')
            
            # Format message with HTML
            message = (
                f"👤 <b>Your Profile</b>\n\n"
                f"<b>Telegram ID:</b> <code>{user.id}</code>\n"
                f"<b>Username:</b> {username}\n\n"
                f"<b>XRP Wallet:</b>\n"
                f"  📬 <b>Address:</b> {format_xrp_address(wallet_address)}\n"
                f"  💰 <b>Balance:</b> {balance_xrp:.6f} XRP\n"
                f"  📊 <b>Total Transactions:</b> {tx_count}\n\n"
            )
            
            # Add funding guidance if balance is low
            if balance_xrp < 20:
                message += (
                    f"⚠️ <b>Wallet needs funding to transact</b>\n"
                    f"Visit: <a href='https://xrpl.org/xrp-testnet-faucet.html'>XRPL Testnet Faucet</a>\n\n"
                )
            
            message += "Use /balance for detailed funding instructions."
            
            # Add inline keyboard
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("💰 Balance", callback_data="balance"),
                    InlineKeyboardButton("⚙️ Settings", callback_data="settings")
                ],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ])
            
            await reply_func(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            error_msg = "❌ <b>Not Registered</b>\n\nYou need to register first!\nUse /start to create your wallet."
        else:
            error_msg = f"A server error occurred: {e.response.status_code}"
        await reply_func(error_msg, parse_mode=ParseMode.HTML)
        
    except Exception as e:
        error_msg = format_error_message(f"Could not retrieve profile: {str(e)}")
        await reply_func(error_msg, parse_mode=ParseMode.HTML)
