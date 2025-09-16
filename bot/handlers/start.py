# bot/handlers/start.py
import logging

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..keyboards.menus import keyboards
from ..utils.formatting import (
    escape_html,
    format_error_message,
    format_funding_instructions,
    format_success_message,
    format_xrp_address,
)

logger = logging.getLogger(__name__)


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
        parse_mode=ParseMode.HTML,
    )

    # Prepare user data for the backend API
    user_data = {
        "telegram_id": str(user.id),
        "telegram_username": user.username,
        "telegram_first_name": user.first_name,
        "telegram_last_name": user.last_name,
    }

    try:
        # Call backend API to register the user and get wallet details
        async with httpx.AsyncClient() as client:
            # Ensure the api_url is correctly passed in your bot's main setup
            api_url = context.bot_data.get("api_url", "http://localhost:8000")
            api_key = context.bot_data.get("api_key", "dev-bot-api-key-change-in-production")

            headers = {"X-API-Key": api_key}
            response = await client.post(
                f"{api_url}/api/v1/user/register", json=user_data, headers=headers, timeout=30.0
            )

        response.raise_for_status()  # Raise an exception for HTTP errors (4xx or 5xx)

        data = response.json()

        # Safely escape the user's name to prevent HTML formatting issues
        safe_first_name = escape_html(user.first_name or "User")

        wallet_address = data.get("xrp_address", "N/A")
        balance = data.get("balance", 0)

        if data.get("is_new"):
            # Message for a newly registered user
            message = format_success_message(
                "Wallet Created Successfully!",
                "📬 <b>Your XRP Address:</b>\n" + format_xrp_address(wallet_address) + "\n\n"
                "💰 <b>Initial Balance:</b> " + f"{float(balance):.6f}" + " XRP\n\n"
                "⚠️ <i>This is a TestNet wallet with TestNet XRP for testing only.</i>",
            )

            # Add funding instructions for new wallets
            funding_instructions = format_funding_instructions(float(balance), is_mainnet=False)
            if funding_instructions:
                message += funding_instructions
                message += "\n\n"

            message += "Type /help to see all available commands."
        else:
            # Message for a returning user
            message = (
                "👋 <b>Welcome back, " + safe_first_name + "!</b>\n\n"
                "📬 <b>Your XRP Address:</b>\n" + format_xrp_address(wallet_address) + "\n\n"
                "💰 <b>Current Balance:</b> " + f"{float(balance):.6f}" + " XRP\n\n"
            )

            # Show funding reminder if balance is low
            if float(balance) < 20:
                message += (
                    "⚠️ <b>Low Balance:</b> Your wallet needs funding to transact.\n"
                    "Use /balance for funding instructions.\n\n"
                )

            message += "What would you like to do today?"

        # Add inline keyboard for quick actions
        keyboard = keyboards.main_menu()
        await update.message.reply_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    except httpx.HTTPStatusError as e:
        # Handle specific HTTP errors from the backend
        error_message = (
            "Failed to communicate with the backend: Server responded with "
            + str(e.response.status_code)
            + "."
        )
        full_error = "Could not set up your wallet. Reason: " + error_message
        await update.message.reply_text(format_error_message(full_error), parse_mode=ParseMode.HTML)
    except Exception as e:
        # Handle other errors like network issues or timeouts
        import traceback

        logger.error(f"Error in start_command: {e}")
        logger.error(f"Traceback: {traceback.format_exc()}")
        error_details = (
            "An Unexpected Error Occurred\n\nRegistration failed. Please try again later.\n\nDetails: "
            + str(e)
        )
        await update.message.reply_text(
            format_error_message(error_details), parse_mode=ParseMode.HTML
        )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command and display available commands."""
    # Handle both message and callback query
    if update.message:
        reply_func = update.message.reply_text
    elif update.callback_query:
        reply_func = update.callback_query.message.edit_text
        await update.callback_query.answer()
    else:
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

    # Add back to main menu button
    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]]
    )

    await reply_func(
        help_text, parse_mode=ParseMode.HTML, disable_web_page_preview=True, reply_markup=keyboard
    )
