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
    """Handle /start command with informed consent and wallet options."""
    user = update.effective_user
    # Ensure the message and user objects exist before proceeding.
    if not update.message or not user:
        return

    # Check if user already exists
    user_exists = False
    try:
        async with httpx.AsyncClient() as client:
            api_url = context.bot_data.get("api_url", "http://localhost:8000")
            api_key = context.bot_data.get("api_key", "dev-bot-api-key-change-in-production")
            headers = {"X-API-Key": api_key}

            # Check if user exists
            response = await client.get(
                f"{api_url}/api/v1/wallet/balance/{user.id}",
                headers=headers,
                timeout=10.0,
            )

            if response.status_code == 200:
                user_exists = True
            elif response.status_code == 404:
                user_exists = False
            else:
                # Other status codes - treat as user doesn't exist for safety
                logger.warning(
                    f"Unexpected status code {response.status_code} when checking user {user.id}"
                )
                user_exists = False

    except Exception as e:
        # User doesn't exist or API error, continue with onboarding
        logger.debug(
            f"User {user.id} not found in system or API error, continuing with onboarding: {e}"
        )
        user_exists = False

    # Route based on user existence
    if user_exists:
        await show_returning_user_welcome(update, context)
        return

    # Show wallet creation options for new users
    safe_first_name = escape_html(user.first_name or "User")

    welcome_message = (
        f"🎉 <b>Welcome to the XRP Ledger Bot, {safe_first_name}!</b>\n\n"
        "To get started, I need to set up an XRP wallet for you. You have two options:\n\n"
        "🔐 <b>What happens when you create a wallet:</b>\n"
        "• A new XRP TestNet wallet will be generated\n"
        "• Your private keys will be encrypted and stored securely\n"
        "• You'll receive a unique XRP address for transactions\n"
        "• Your wallet will be automatically funded with test XRP\n\n"
        "⚠️ <b>Important:</b> This is a TestNet wallet for testing only. "
        "Do not use real XRP or send real value to these addresses.\n\n"
        "Choose how you'd like to proceed:"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🆕 Create New Wallet", callback_data="create_new_wallet")],
            [InlineKeyboardButton("📥 Import Existing Wallet", callback_data="import_wallet")],
            [InlineKeyboardButton("ℹ️ Learn More", callback_data="learn_more_wallets")],
        ]
    )

    await update.message.reply_text(
        welcome_message, parse_mode=ParseMode.HTML, reply_markup=keyboard
    )


async def show_returning_user_welcome(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show welcome message for returning users."""
    user = update.effective_user
    if not user:
        return

    try:
        async with httpx.AsyncClient() as client:
            api_url = context.bot_data.get("api_url", "http://localhost:8000")
            api_key = context.bot_data.get("api_key", "dev-bot-api-key-change-in-production")
            headers = {"X-API-Key": api_key}

            # Get user's wallet balance
            response = await client.get(
                f"{api_url}/api/v1/wallet/balance/{user.id}",
                headers=headers,
                timeout=10.0,
            )

            if response.status_code == 200:
                data = response.json()
                safe_first_name = escape_html(user.first_name or "User")
                wallet_address = data.get("address", "N/A")
                balance = data.get("balance", 0)

                message = (
                    f"👋 <b>Welcome back, {safe_first_name}!</b>\n\n"
                    "📬 <b>Your XRP Address:</b>\n" + format_xrp_address(wallet_address) + "\n\n"
                    f"💰 <b>Current Balance:</b> {float(balance):.6f} XRP\n\n"
                )

                # Show funding reminder if balance is low (adjusted for new reserves)
                if float(balance) < 1:
                    message += (
                        "⚠️ <b>Low Balance:</b> Your wallet needs funding to transact.\n"
                        "Use /balance for funding instructions or to request more TestNet XRP.\n\n"
                    )

                message += "What would you like to do today?"

                # Add inline keyboard for quick actions
                keyboard = keyboards.main_menu()
                if update.message:
                    await update.message.reply_text(
                        message, parse_mode=ParseMode.HTML, reply_markup=keyboard
                    )
            else:
                if update.message:
                    await update.message.reply_text(
                        format_error_message(
                            "Could not fetch your wallet information. Please try again."
                        ),
                        parse_mode=ParseMode.HTML,
                    )

    except Exception as e:
        logger.error(f"Error in show_returning_user_welcome: {e}")
        if update.message:
            await update.message.reply_text(
                format_error_message("An error occurred. Please try again."),
                parse_mode=ParseMode.HTML,
            )


async def handle_create_new_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):  # noqa: ARG001
    """Handle creating a new wallet with funding options."""
    query = update.callback_query
    if not query or not query.message:
        return

    await query.answer()
    user = update.effective_user
    if not user:
        return

    # Show funding options
    funding_message = (
        "🔧 <b>Wallet Funding Options</b>\n\n"
        "How would you like to fund your new wallet?\n\n"
        "💰 <b>Auto-Fund:</b> Automatically request 10 TestNet XRP from the faucet\n"
        "🎯 <b>Manual:</b> I'll create the wallet and you can fund it yourself\n\n"
        "Choose your preferred option:"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "💰 Auto-Fund (10 XRP)",
                    callback_data="create_wallet_auto",
                )
            ],
            [
                InlineKeyboardButton(
                    "🎯 Manual (No Auto-Fund)",
                    callback_data="create_wallet_manual",
                )
            ],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")],
        ]
    )

    await query.edit_message_text(funding_message, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def handle_wallet_creation(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,
    auto_fund: bool = True,
):
    """Handle the actual wallet creation process."""
    query = update.callback_query
    if not query or not query.message:
        return

    user = update.effective_user
    if not user:
        return

    # Show processing message
    await query.edit_message_text(
        "⏳ <b>Creating your wallet...</b>\n\nPlease wait while I set up your XRP wallet.",
        parse_mode=ParseMode.HTML,
    )

    # Prepare user data for the backend API
    user_data = {
        "telegram_id": str(user.id),
        "telegram_username": user.username,
        "telegram_first_name": user.first_name,
        "telegram_last_name": user.last_name,
        "auto_fund": auto_fund,
    }

    try:
        async with httpx.AsyncClient() as client:
            api_url = context.bot_data.get("api_url", "http://localhost:8000")
            api_key = context.bot_data.get("api_key", "dev-bot-api-key-change-in-production")

            headers = {"X-API-Key": api_key}
            response = await client.post(
                f"{api_url}/api/v1/user/register",
                json=user_data,
                headers=headers,
                timeout=30.0,
            )

        response.raise_for_status()
        data = response.json()

        safe_first_name = escape_html(user.first_name or "User")
        wallet_address = data.get("xrp_address", "N/A")
        balance = data.get("balance", 0)

        # Create success message
        message = format_success_message(
            "✅ Wallet Created Successfully!",
            f"🎉 <b>Welcome to XRP Ledger, {safe_first_name}!</b>\n\n"
            "📬 <b>Your XRP Address:</b>\n" + format_xrp_address(wallet_address) + "\n\n"
            f"💰 <b>Current Balance:</b> {float(balance):.6f} XRP\n\n"
            "⚠️ <i>This is a TestNet wallet with TestNet XRP for testing only.</i>",
        )

        # Add funding instructions if needed
        if not auto_fund or float(balance) < 1:
            funding_instructions = format_funding_instructions(float(balance), is_mainnet=False)
            if funding_instructions:
                message += "\n\n" + funding_instructions

        message += "\n\nType /help to see all available commands."

        # Add main menu keyboard
        keyboard = keyboards.main_menu()
        await query.edit_message_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    except httpx.HTTPStatusError as e:
        error_message = f"Failed to create wallet: Server responded with {e.response.status_code}."
        await query.edit_message_text(
            format_error_message(error_message), parse_mode=ParseMode.HTML
        )
    except Exception as e:
        logger.error(f"Error in handle_wallet_creation: {e}")
        await query.edit_message_text(
            format_error_message("An unexpected error occurred. Please try again later."),
            parse_mode=ParseMode.HTML,
        )


async def handle_import_wallet(update: Update, context: ContextTypes.DEFAULT_TYPE):  # noqa: ARG001
    """Handle importing an existing wallet."""
    query = update.callback_query
    if not query or not query.message:
        return

    await query.answer()

    import_message = (
        "📥 <b>Import Existing Wallet</b>\n\n"
        "To import your existing XRP wallet, I'll need your wallet's secret/seed phrase.\n\n"
        "⚠️ <b>Security Notice:</b>\n"
        "• Your secret will be encrypted before storage\n"
        "• Only import TestNet wallets for safety\n"
        "• Never share your secret with anyone else\n\n"
        "🔒 <b>How to import:</b>\n"
        "1. Click 'Proceed' below\n"
        "2. Send me your wallet secret in the next message\n"
        "3. I'll validate and import your wallet\n\n"
        "Ready to proceed?"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔒 Proceed with Import", callback_data="proceed_import")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")],
        ]
    )

    await query.edit_message_text(import_message, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def handle_learn_more(update: Update, context: ContextTypes.DEFAULT_TYPE):  # noqa: ARG001
    """Show educational information about XRP wallets."""
    query = update.callback_query
    if not query or not query.message:
        return

    await query.answer()

    learn_more_message = (
        "📚 <b>Learn About XRP Wallets</b>\n\n"
        "🔐 <b>What is an XRP Wallet?</b>\n"
        "An XRP wallet contains:\n"
        "• A public address (like an email address)\n"
        "• A private secret/key (like a password)\n"
        "• Your XRP balance and transaction history\n\n"
        "🌐 <b>TestNet vs MainNet:</b>\n"
        "• TestNet: For testing, uses fake XRP\n"
        "• MainNet: Real network with real XRP value\n\n"
        "💰 <b>Account Reserve:</b>\n"
        "• XRP accounts require a 10 XRP minimum reserve\n"
        "• This reserve cannot be spent\n"
        "• It keeps your account active on the network\n\n"
        "🔒 <b>Security:</b>\n"
        "• Never share your wallet secret\n"
        "• Your secret is encrypted when stored\n"
        "• Keep backups of important wallet secrets\n\n"
        "Ready to create your wallet?"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🆕 Create New Wallet", callback_data="create_new_wallet")],
            [InlineKeyboardButton("📥 Import Existing", callback_data="import_wallet")],
            [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")],
        ]
    )

    await query.edit_message_text(
        learn_more_message, parse_mode=ParseMode.HTML, reply_markup=keyboard
    )


# Callback handlers for different wallet creation options
async def handle_create_wallet_auto(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle auto-funded wallet creation."""
    await handle_wallet_creation(update, context, auto_fund=True)


async def handle_create_wallet_manual(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle manual wallet creation (no auto-funding)."""
    await handle_wallet_creation(update, context, auto_fund=False)


async def handle_back_to_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle back to start navigation."""
    query = update.callback_query
    if not query or not query.message:
        return

    await query.answer()

    # Clear any user state
    if context.user_data:
        context.user_data.clear()

    # Restart the start command flow
    await start_command(update, context)


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):  # noqa: ARG001
    """Handle /help command and display available commands."""
    # Handle both message and callback query
    if update.message:
        reply_func = update.message.reply_text
    elif update.callback_query and update.callback_query.message:
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
        help_text,
        parse_mode=ParseMode.HTML,
        disable_web_page_preview=True,
        reply_markup=keyboard,
    )
