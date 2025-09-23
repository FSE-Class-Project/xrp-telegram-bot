# bot/handlers/start.py
import logging
import os

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..constants import ACCOUNT_RESERVE, FAUCET_AMOUNT
from ..keyboards.menus import keyboards
from ..utils.formatting import (
    escape_html,
    format_error_message,
    format_error_message_with_title,
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
        f"💰 <b>Auto-Fund:</b> Automatically request {FAUCET_AMOUNT} TestNet XRP from the faucet\n"
        "🎯 <b>Manual:</b> I'll create the wallet and you can fund it yourself\n\n"
        "Choose your preferred option:"
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    f"💰 Auto-Fund ({FAUCET_AMOUNT} XRP)",
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
        "⚠️ <b>CRITICAL SAFETY WARNING</b> ⚠️\n\n"
        "🚨 <b>TESTNET ONLY:</b> This bot is for TestNet only!\n"
        "• Do NOT import wallets with real MainNet XRP\n"
        "• Do NOT import your primary/main wallet\n"
        "• Use only TestNet wallets or empty wallets\n\n"
        "🔒 <b>Security Measures:</b>\n"
        "• We check MainNet for existing funds\n"
        "• Wallets with MainNet XRP will be REJECTED\n"
        "• Your secret will be encrypted before storage\n"
        "• All operations are TestNet only\n\n"
        "💡 <b>Recommended:</b> Create a new TestNet wallet instead\n\n"
        "Only proceed if you understand these risks and have a TestNet-only wallet."
    )

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton(
                    "🚨 I Understand - TestNet Only", callback_data="confirm_testnet_import"
                )
            ],
            [
                InlineKeyboardButton(
                    "✨ Create New Wallet Instead", callback_data="create_new_wallet"
                )
            ],
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
        f"• XRP accounts require a {ACCOUNT_RESERVE} XRP minimum reserve\n"
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


# Wallet import conversation states
WAITING_FOR_PRIVATE_KEY = "waiting_for_private_key"


async def handle_confirm_testnet_import(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle proceeding with wallet import."""
    query = update.callback_query
    if not query or not query.message:
        return

    await query.answer()

    # Set conversation state
    context.user_data["import_state"] = WAITING_FOR_PRIVATE_KEY

    proceed_message = (
        "🔐 <b>Final Step: Send Your TestNet Wallet</b>\n\n"
        "🔍 <b>Safety Check Process:</b>\n"
        "1. I'll validate your wallet format\n"
        "2. Check for MainNet funds (WILL REJECT if found)\n"
        "3. Verify it's safe for TestNet use\n"
        "4. Import only if all checks pass\n\n"
        "📤 <b>Send your wallet credentials now:</b>\n"
        "• Private key (starts with 'ED', 'sEd', or 's')\n"
        "• Seed phrase (12-24 words)\n\n"
        "⚠️ <b>Your message will be deleted immediately for security</b>\n\n"
        "🛡️ Remember: TestNet wallets only!"
    )

    keyboard = InlineKeyboardMarkup(
        [[InlineKeyboardButton("❌ Cancel Import", callback_data="back_to_start")]]
    )

    await query.edit_message_text(proceed_message, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def handle_wallet_import_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle receiving the private key/seed phrase for import."""
    if not update.message or not update.message.text:
        return

    # Check if user is in import state
    user_data = context.user_data
    if user_data.get("import_state") != WAITING_FOR_PRIVATE_KEY:
        return

    # Clear the import state immediately
    user_data.pop("import_state", None)

    private_input = update.message.text.strip()
    user = update.effective_user

    # Delete the user's message for security
    try:
        await update.message.delete()
    except Exception as e:
        logger.warning(f"Could not delete user message: {e}")

    # Show processing message
    processing_msg = await update.message.reply_text(
        "🔄 <b>Processing wallet import...</b>\n\nValidating and importing your wallet...",
        parse_mode=ParseMode.HTML,
    )

    try:
        # Import the wallet using backend API
        import httpx

        backend_url = os.getenv("BACKEND_URL", "http://localhost:8000")

        async with httpx.AsyncClient() as client:
            response = await client.post(
                f"{backend_url}/api/users/import-wallet",
                json={
                    "telegram_id": str(user.id),
                    "telegram_username": user.username,
                    "telegram_first_name": user.first_name,
                    "telegram_last_name": user.last_name,
                    "private_key": private_input,
                },
                timeout=30.0,
            )

            if response.status_code == 200:
                data = response.json()

                # Build success message with validation info
                message_lines = [
                    f"Address: {format_xrp_address(data['wallet']['xrp_address'])}",
                    f"TestNet Balance: {data['wallet']['balance']:.6f} XRP",
                    "",
                ]

                # Add validation warnings if any
                validation = data.get("validation", {})
                if validation.get("warnings"):
                    message_lines.append("⚠️ Safety Warnings:")
                    for warning in validation["warnings"]:
                        message_lines.append(f"• {warning}")
                    message_lines.append("")

                message_lines.extend(
                    [
                        "✅ Wallet passed all safety checks",
                        "🔒 Your wallet has been imported and encrypted securely",
                        "🎉 You can now use all bot features with your imported wallet!",
                    ]
                )

                success_message = format_success_message(
                    "Wallet Imported Successfully!", message_lines
                )

                keyboard = InlineKeyboardMarkup(
                    [[InlineKeyboardButton("🏠 Continue to Main Menu", callback_data="main_menu")]]
                )

                await processing_msg.edit_text(
                    success_message, parse_mode=ParseMode.HTML, reply_markup=keyboard
                )

            else:
                error_data = response.json()
                error_message = format_error_message_with_title(
                    "Import Failed",
                    [
                        error_data.get("detail", "Unknown error occurred"),
                        "",
                        "Please check your private key/seed phrase and try again.",
                        "Make sure you're using a valid XRP TestNet wallet.",
                    ],
                )

                keyboard = InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("🔄 Try Again", callback_data="import_wallet")],
                        [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")],
                    ]
                )

                await processing_msg.edit_text(
                    error_message, parse_mode=ParseMode.HTML, reply_markup=keyboard
                )

    except Exception as e:
        logger.error(f"Error importing wallet: {e}")
        error_message = format_error_message_with_title(
            "Import Error",
            [
                "Failed to connect to wallet service.",
                "Please try again later or contact support.",
            ],
        )

        keyboard = InlineKeyboardMarkup(
            [
                [InlineKeyboardButton("🔄 Try Again", callback_data="import_wallet")],
                [InlineKeyboardButton("⬅️ Back", callback_data="back_to_start")],
            ]
        )

        await processing_msg.edit_text(
            error_message, parse_mode=ParseMode.HTML, reply_markup=keyboard
        )
