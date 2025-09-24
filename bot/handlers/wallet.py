# bot/handlers/wallet.py
import logging

import httpx
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..keyboards.menus import keyboards
from ..utils.formatting import (
    format_balance_info,
    format_error_message,
    format_funding_instructions,
    format_username,
    format_xrp_address,
)

logger = logging.getLogger(__name__)


async def balance_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /balance command using HTML formatting."""
    # Handle both message and callback query
    if update.message:
        reply_func = update.message.reply_text
        user_id = update.effective_user.id if update.effective_user else None
    elif update.callback_query and update.callback_query.message:
        reply_func = update.callback_query.message.edit_text
        await update.callback_query.answer()
        user_id = update.callback_query.from_user.id
    else:
        return

    if not user_id:
        return

    try:
        async with httpx.AsyncClient() as client:
            api_url = context.bot_data.get("api_url", "http://localhost:8000")
            api_key = context.bot_data.get("api_key", "dev-bot-api-key-change-in-production")

            headers = {"X-API-Key": api_key}
            # Get balance from API
            response = await client.get(
                f"{api_url}/api/v1/wallet/balance/{user_id}", headers=headers
            )
            response.raise_for_status()  # Raise HTTP errors

            balance_data = response.json()

            # Get user settings to determine display currency
            settings_resp = await client.get(
                f"{api_url}/api/v1/user/settings/{user_id}", headers=headers
            )
            settings_json = settings_resp.json() if settings_resp.status_code == 200 else {}
            currency = settings_json.get("currency_display", "USD").upper()
            timezone_code = settings_json.get("timezone", "UTC")

            # Get current price (multi-currency supported by backend)
            price_response = await client.get(f"{api_url}/api/v1/price/current", headers=headers)
            price_data = price_response.json() if price_response.status_code == 200 else {}

            balance_xrp = float(balance_data.get("balance", 0))
            available_balance = float(balance_data.get("available_balance", 0))
            # Determine per-currency XRP price
            currency_key = {
                "USD": "price_usd",
                "EUR": "price_eur",
                "GBP": "price_gbp",
                "ZAR": "price_zar",
                "JPY": "price_jpy",
                "BTC": "price_btc",
                "ETH": "price_eth",
            }.get(currency, "price_usd")
            price_per_xrp = float(price_data.get(currency_key, price_data.get("price_usd", 0)))
            display_value = balance_xrp * price_per_xrp
            wallet_address = balance_data.get("address", "N/A")

            # Format message using utility functions
            message = format_balance_info(
                address=wallet_address,
                balance=balance_xrp,
                available=available_balance,
                fiat_value=display_value,
                fiat_currency=currency,
                last_updated=balance_data.get("last_updated"),
                timezone_code=timezone_code,
            )

            # Add funding guidance if needed
            funding_instructions = format_funding_instructions(balance_xrp, is_mainnet=False)
            if funding_instructions:
                message += funding_instructions

            # Use shared wallet menu (includes Back + Main)
            await reply_func(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboards.wallet_menu(),
            )

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            error_msg = (
                "❌ <b>Not Registered</b>\n\n"
                "You need to register first!\n"
                "Use /start to create your wallet."
            )
        else:
            error_msg = f"A server error occurred: {e.response.status_code}"
        await reply_func(error_msg, parse_mode=ParseMode.HTML)

    except Exception as e:
        error_msg = format_error_message(f"Could not retrieve balance: {str(e)}")
        await reply_func(error_msg, parse_mode=ParseMode.HTML)


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /profile command using HTML formatting."""
    # Handle both message and callback query
    if update.message:
        reply_func = update.message.reply_text
        user = update.effective_user
    elif update.callback_query and update.callback_query.message:
        reply_func = update.callback_query.message.edit_text
        await update.callback_query.answer()
        user = update.callback_query.from_user
    else:
        return

    if not user:
        return

    try:
        async with httpx.AsyncClient() as client:
            api_url = context.bot_data.get("api_url", "http://localhost:8000")
            api_key = context.bot_data.get("api_key", "dev-bot-api-key-change-in-production")

            headers = {"X-API-Key": api_key}
            # Get user wallet data
            response = await client.get(
                f"{api_url}/api/v1/wallet/balance/{user.id}", headers=headers
            )
            response.raise_for_status()
            wallet_data = response.json()

            # Get transaction count
            tx_response = await client.get(
                f"{api_url}/api/v1/transaction/history/{user.id}",
                headers=headers,
            )
            tx_count = (
                len(tx_response.json().get("transactions", []))
                if tx_response.status_code == 200
                else 0
            )

            username = format_username(user.username)

            balance_xrp = float(wallet_data.get("balance", 0))
            wallet_address = wallet_data.get("address", "N/A")

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
            if balance_xrp < 1:
                message += (
                    "⚠️ <b>Wallet needs funding to transact</b>\n"
                    "Visit: <a href='https://test.bithomp.com/en/faucet'>"
                    "XRPL Testnet Faucet</a>\n\n"
                )

            message += "Use /balance for detailed funding instructions."

            # Use shared profile menu (includes Back + Main)
            await reply_func(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboards.profile_menu(),
            )

    except httpx.HTTPStatusError as e:
        if e.response.status_code == 404:
            error_msg = (
                "❌ <b>Not Registered</b>\n\n"
                "You need to register first!\n"
                "Use /start to create your wallet."
            )
        else:
            error_msg = f"A server error occurred: {e.response.status_code}"
        await reply_func(error_msg, parse_mode=ParseMode.HTML)

    except Exception as e:
        error_msg = format_error_message(f"Could not retrieve profile: {str(e)}")
        await reply_func(error_msg, parse_mode=ParseMode.HTML)
