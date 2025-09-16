# bot/handlers/account.py
"""Account management handlers for deletion, help, and support."""

from typing import Optional, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
import httpx
import logging

from ..utils.formatting import (
    escape_html,
    format_error_message,
    format_success_message,
)

logger = logging.getLogger(__name__)


async def confirm_delete_account(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle confirmed account deletion."""
    query = update.callback_query
    if not query:
        return

    await query.answer()
    user_id = query.from_user.id

    try:
        api_url = context.bot_data.get("api_url", "http://localhost:8000")
        api_key = context.bot_data.get("api_key", "dev-bot-api-key-change-in-production")

        # Delete account via API
        async with httpx.AsyncClient() as client:
            headers = {"X-API-Key": api_key}
            response = await client.delete(
                f"{api_url}/api/v1/user/{user_id}", headers=headers, timeout=30.0
            )

            if response.status_code == 200:
                message = """
✅ <b>Account Deleted Successfully</b>

Your XRP Telegram Bot account has been permanently deleted.

<b>What was deleted:</b>
• Your wallet and private keys
• All transaction history  
• Personal settings and data
• Cached information

<b>Thank you for using XRP Telegram Bot!</b>

If you ever want to use the bot again, simply send /start to create a new account.

<i>This conversation will remain, but all your bot data has been removed.</i>
"""

                if query.message:
                    await query.message.edit_text(message, parse_mode=ParseMode.HTML)

                # Log the deletion
                logger.warning(f"Account deleted for user {user_id} via Telegram bot")

            else:
                error_data = response.json() if response.status_code != 500 else {}
                error_message = error_data.get("detail", "Unknown error occurred")

                await query.answer("Account deletion failed", show_alert=True)
                if query.message:
                    await query.message.edit_text(
                        format_error_message(
                            f"Deletion Failed: Could not delete your account: {error_message}\\n\\n"
                            "Please try again or contact support if the problem persists."
                        ),
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(
                            [
                                [
                                    InlineKeyboardButton(
                                        "🔄 Try Again", callback_data="delete_account"
                                    )
                                ],
                                [InlineKeyboardButton("🔙 Back to Settings", callback_data="back")],
                            ]
                        ),
                    )

    except Exception as e:
        logger.error(f"Error deleting account for user {user_id}: {e}", exc_info=True)
        await query.answer("An error occurred during deletion", show_alert=True)
        if query.message:
            await query.message.edit_text(
                format_error_message(
                    "Deletion Error: An unexpected error occurred. Please try again later or contact support."
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("🔄 Try Again", callback_data="delete_account")],
                        [InlineKeyboardButton("🔙 Back to Settings", callback_data="back")],
                    ]
                ),
            )


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /help command."""
    user_id = update.effective_user.id if update.effective_user else None

    message = """
🆘 <b>XRP Telegram Bot Help</b>

<b>Getting Started:</b>
• Send /start to create your wallet
• Your wallet is automatically funded with TestNet XRP

<b>Available Commands:</b>
• /balance - Check your XRP balance
• /send - Send XRP to another address  
• /price - View current XRP price
• /history - View transaction history
• /settings - Manage bot settings
• /profile - View your profile info
• /help - Show this help message

<b>Sending XRP:</b>
You can send XRP in two ways:
1. <code>/send 10 rN7n7otQDd6FczFgLdSqDtD2XZzWjfrn96</code>
2. Use /send and follow the interactive prompts

<b>Safety Tips:</b>
• This bot operates on XRP TestNet (test funds only)
• TestNet XRP has no real monetary value
• Always verify recipient addresses before sending
• Enable PIN protection in settings for extra security

<b>Need Support?</b>
Contact our support team for assistance!
"""

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("💰 Check Balance", callback_data="balance"),
                InlineKeyboardButton("💸 Send XRP", callback_data="send_xrp"),
            ],
            [
                InlineKeyboardButton("📊 View Price", callback_data="price"),
                InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
            ],
            [
                InlineKeyboardButton("📞 Contact Support", callback_data="contact_support"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"),
            ],
        ]
    )

    if update.message:
        await update.message.reply_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)
    elif update.callback_query:
        await update.callback_query.answer()
        if update.callback_query.message:
            await update.callback_query.message.edit_text(
                message, parse_mode=ParseMode.HTML, reply_markup=keyboard
            )


async def contact_support(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle support contact request."""
    query = update.callback_query
    if not query:
        return

    await query.answer()

    message = """
📞 <b>Contact Support</b>

Need help? We're here for you!

<b>Support Options:</b>

🔸 <b>Email Support</b>
Send us an email: support@fse-group3.co.za

🔸 <b>FAQ & Documentation</b>  
Check our comprehensive FAQ for common questions

🔸 <b>Bug Reports</b>
Report technical issues on GitHub

🔸 <b>Project Board</b>
View development progress and updates

<b>Before contacting support:</b>
• Check if /help answers your question
• Try restarting the bot with /start
• Note any error messages you received

<b>Response Time:</b> Usually within 24 hours

<i>Please include your Telegram username and describe your issue clearly.</i>
"""

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("📧 Email Support", url="mailto:support@fse-group3.co.za"),
                InlineKeyboardButton(
                    "📚 FAQ",
                    url="https://github.com/FSE-Class-Project/xrp-telegram-bot/blob/main/FAQ.md",
                ),
            ],
            [
                InlineKeyboardButton(
                    "🐛 Report Bug",
                    url="https://github.com/FSE-Class-Project/xrp-telegram-bot/issues",
                ),
                InlineKeyboardButton(
                    "📊 Project Board",
                    url="https://github.com/orgs/FSE-Class-Project/projects/1/views/1",
                ),
            ],
            [
                InlineKeyboardButton("🆘 Help", callback_data="help"),
                InlineKeyboardButton("🔙 Back", callback_data="main_menu"),
            ],
        ]
    )

    if query.message:
        await query.message.edit_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def withdraw_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /withdraw command - alias for /send."""
    # Simply call the send command since withdrawal is the same as sending
    from .transaction import send_command

    await send_command(update, context)


async def profile_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /profile command."""
    user = update.effective_user
    if not user:
        return

    try:
        api_url = context.bot_data.get("api_url", "http://localhost:8000")
        api_key = context.bot_data.get("api_key", "dev-bot-api-key-change-in-production")

        # Fetch user profile data
        async with httpx.AsyncClient() as client:
            headers = {"X-API-Key": api_key}

            # Get user settings (includes profile info)
            settings_response = await client.get(
                f"{api_url}/api/v1/user/settings/{user.id}", headers=headers, timeout=10.0
            )

            # Get wallet balance
            balance_response = await client.get(
                f"{api_url}/api/v1/wallet/balance/{user.id}", headers=headers, timeout=10.0
            )

            if settings_response.status_code == 200 and balance_response.status_code == 200:
                settings_data = settings_response.json()
                balance_data = balance_response.json()

                # Format creation date
                created_at = settings_data.get("created_at", "Unknown")
                if created_at != "Unknown":
                    try:
                        from datetime import datetime

                        created_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                        created_formatted = created_date.strftime("%Y-%m-%d")
                    except:
                        created_formatted = created_at[:10]
                else:
                    created_formatted = "Unknown"

                message = f"""
👤 <b>Your Profile</b>

<b>Account Info:</b>
• Name: {escape_html(user.first_name or 'N/A')} {escape_html(user.last_name or '')}
• Username: @{escape_html(user.username or 'None')}
• Telegram ID: <code>{user.id}</code>
• Joined: {created_formatted}

<b>Wallet Info:</b>
• Balance: {balance_data.get('balance', 0):.6f} XRP
• Address: <code>{balance_data.get('address', 'N/A')}</code>
• Network: XRP TestNet

<b>Settings:</b>
• Price Alerts: {'✅' if settings_data.get('price_alerts', False) else '❌'}
• TX Notifications: {'✅' if settings_data.get('transaction_notifications', True) else '❌'}
• Currency: {settings_data.get('currency_display', 'USD')}
• 2FA: {'✅' if settings_data.get('two_factor_enabled', False) else '❌'}

<i>Manage your settings and preferences below.</i>
"""

                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton("💰 Balance", callback_data="balance"),
                            InlineKeyboardButton("💸 Send XRP", callback_data="send_xrp"),
                        ],
                        [
                            InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
                            InlineKeyboardButton("📊 History", callback_data="history"),
                        ],
                        [
                            InlineKeyboardButton("🆘 Help", callback_data="help"),
                            InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"),
                        ],
                    ]
                )

            else:
                message = format_error_message(
                    "Profile Unavailable: Could not load your profile information. Please try again later."
                )
                keyboard = InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("🔄 Try Again", callback_data="profile")],
                        [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")],
                    ]
                )

            if update.message:
                await update.message.reply_text(
                    message, parse_mode=ParseMode.HTML, reply_markup=keyboard
                )
            elif update.callback_query:
                await update.callback_query.answer()
                if update.callback_query.message:
                    await update.callback_query.message.edit_text(
                        message, parse_mode=ParseMode.HTML, reply_markup=keyboard
                    )

    except Exception as e:
        logger.error(f"Error in profile_command: {e}", exc_info=True)
        error_message = format_error_message(
            "Profile Error: An error occurred while loading your profile."
        )

        if update.message:
            await update.message.reply_text(error_message, parse_mode=ParseMode.HTML)
        elif update.callback_query:
            await update.callback_query.answer("Profile error", show_alert=True)
