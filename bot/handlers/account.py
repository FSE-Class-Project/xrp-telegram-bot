# bot/handlers/account.py
"""Account management handlers for deletion, help, and support."""

import logging

import httpx
from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..utils.formatting import (
    escape_html,
    format_error_message,
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
                f"{api_url}/api/v1/user/{user_id}",
                headers=headers,
                timeout=30.0,
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

If you ever want to use the bot again, simply send /start to create
a new account.

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
                            f"Deletion Failed: Could not delete your account: "
                            f"{error_message}\\n\\n"
                            "Please try again or contact support if the "
                            "problem persists."
                        ),
                        parse_mode=ParseMode.HTML,
                        reply_markup=InlineKeyboardMarkup(
                            [
                                [
                                    InlineKeyboardButton(
                                        "🔄 Try Again",
                                        callback_data="delete_account",
                                    )
                                ],
                                [
                                    InlineKeyboardButton(
                                        "🔙 Back to Settings",
                                        callback_data="back",
                                    )
                                ],
                            ]
                        ),
                    )

    except Exception as e:
        logger.error(f"Error deleting account for user {user_id}: {e}", exc_info=True)
        await query.answer("An error occurred during deletion", show_alert=True)
        if query.message:
            await query.message.edit_text(
                format_error_message(
                    "Deletion Error: An unexpected error occurred. "
                    "Please try again later or contact support."
                ),
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(
                    [
                        [InlineKeyboardButton("🔄 Try Again", callback_data="delete_account")],
                        [InlineKeyboardButton("🔙 Back to Settings", callback_data="back")],
                    ]
                ),
            )


async def help_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,  # noqa: ARG001
) -> None:
    """Handle /help command."""
    # user_id = update.effective_user.id if update.effective_user else None

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


async def contact_support(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,  # noqa: ARG001
) -> None:
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

            # Get user settings
            settings_response = await client.get(
                f"{api_url}/api/v1/user/settings/{user.id}",
                headers=headers,
                timeout=10.0,
            )

            # Get wallet balance
            balance_response = await client.get(
                f"{api_url}/api/v1/wallet/balance/{user.id}",
                headers=headers,
                timeout=10.0,
            )

            # Get user profile data from export endpoint
            # (includes stored username)
            profile_response = await client.post(
                f"{api_url}/api/v1/user/export/{user.id}",
                headers=headers,
                timeout=10.0,
            )

            if settings_response.status_code == 200 and balance_response.status_code == 200:
                settings_data = settings_response.json()
                balance_data = balance_response.json()

                # Get stored user data, fallback to current Telegram data
                stored_username = None
                stored_first_name = None
                stored_last_name = None
                created_formatted = "Unknown"

                if profile_response.status_code == 200:
                    profile_data = profile_response.json()
                    stored_username = profile_data.get("telegram_username")
                    # Format creation date from profile data
                    created_at = profile_data.get("created_at", "Unknown")
                    if created_at != "Unknown":
                        try:
                            from datetime import datetime

                            created_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                            created_formatted = created_date.strftime("%Y-%m-%d")
                        except (ValueError, TypeError, AttributeError):
                            created_formatted = str(created_at)[:10]
                else:
                    # Fallback to settings creation date
                    created_at = settings_data.get("created_at", "Unknown")
                    if created_at != "Unknown":
                        try:
                            from datetime import datetime

                            created_date = datetime.fromisoformat(created_at.replace("Z", "+00:00"))
                            created_formatted = created_date.strftime("%Y-%m-%d")
                        except (ValueError, TypeError, AttributeError):
                            created_formatted = str(created_at)[:10]

                # Use stored data if available, fallback to current
                # Telegram data
                display_username = stored_username or user.username
                display_first_name = stored_first_name or user.first_name
                display_last_name = stored_last_name or user.last_name

                balance_value = float(balance_data.get("balance") or 0)
                address_value = balance_data.get("address") or "N/A"
                address_html = escape_html(address_value)

                notifications_enabled = settings_data.get("transaction_notifications", True)
                price_alerts_enabled = settings_data.get("price_alerts", False)
                two_factor_enabled = settings_data.get("two_factor_enabled", False)
                currency_display = settings_data.get("currency_display", "USD")

                username_text = (
                    f"@{escape_html(display_username)}"
                    if display_username
                    else f"Not Set@{escape_html(display_username)}"
                    if display_username
                    else "Not Set"
                )

                created_text = escape_html(created_formatted)
                currency_text = escape_html(str(currency_display))

                message = (
                    "👤 <b>Your Profile</b>\n\n"
                    "<b>Account Info:</b>\n"
                    f"• Name: {escape_html(display_first_name or 'N/A')} "
                    f"{escape_html(display_last_name or '')}\n"
                    f"• Username: {username_text}\n"
                    f"• Telegram ID: <code>{user.id}</code>\n"
                    f"• Joined: {created_text}\n\n"
                    "<b>Wallet Info:</b>\n"
                    f"• Balance: {balance_value:.6f} XRP\n"
                    f"• Address: <code>{address_html}</code>\n"
                    "• Network: XRP TestNet\n\n"
                    "<b>Settings:</b>\n"
                    f"• Price Alerts: {'✅' if price_alerts_enabled else '❌'}\n"
                    f"• TX Notifications: {'✅' if notifications_enabled else '❌'}\n"
                    f"• Currency: {currency_text}\n"
                    f"• 2FA: {'✅' if two_factor_enabled else '❌'}\n\n"
                    "<i>Manage your settings and preferences below.</i>"
                )

                keyboard = InlineKeyboardMarkup(
                    [
                        [
                            InlineKeyboardButton("💰 Balance", callback_data="balance"),
                            InlineKeyboardButton("💸 Send XRP", callback_data="send_xrp"),
                        ],
                        [
                            InlineKeyboardButton("✏️ Edit Profile", callback_data="edit_profile"),
                            InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
                        ],
                        [
                            InlineKeyboardButton("📊 History", callback_data="history"),
                            InlineKeyboardButton("🆘 Help", callback_data="help"),
                        ],
                        [
                            InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"),
                        ],
                    ]
                )

            else:
                message = format_error_message(
                    "Profile Unavailable: Could not load your profile "
                    "information. Please try again later."
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
                        message,
                        parse_mode=ParseMode.HTML,
                        reply_markup=keyboard,
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


async def edit_profile_command(
    update: Update,
    context: ContextTypes.DEFAULT_TYPE,  # noqa: ARG001
) -> None:
    """Handle edit profile command/callback."""
    query = update.callback_query
    if not query:
        return

    await query.answer()
    # user = query.from_user  # Not needed in this function

    message = """
✏️ <b>Edit Profile</b>

You can update your profile information below.

<b>Available Updates:</b>
• Username: Change your display name
• Current username from registration will be shown

<b>Note:</b> Your Telegram account details (first name, last name)
are managed by Telegram and cannot be changed here.

Choose what you'd like to update:
"""

    keyboard = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("📝 Update Username", callback_data="update_username")],
            [InlineKeyboardButton("🔄 Sync from Telegram", callback_data="sync_telegram_data")],
            [
                InlineKeyboardButton("🔙 Back to Profile", callback_data="profile"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"),
            ],
        ]
    )

    if query.message:
        await query.message.edit_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)


async def update_username_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle update username command."""
    query = update.callback_query
    if not query:
        return

    await query.answer()

    message = """
📝 <b>Update Username</b>

Please send me your new username.

<b>Guidelines:</b>
• Can contain letters, numbers, and underscores
• No @ symbol needed (will be added automatically)
• 3-32 characters long
• Example: "john_doe" or "crypto_trader"

<b>Current username:</b> Will be shown in your profile

Send your new username in the next message, or use the buttons below:
"""

    keyboard = InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔙 Back", callback_data="edit_profile"),
                InlineKeyboardButton("❌ Cancel", callback_data="profile"),
            ],
        ]
    )

    if query.message:
        await query.message.edit_text(message, parse_mode=ParseMode.HTML, reply_markup=keyboard)

    # Set user state to expect username input
    if context.user_data is not None:
        context.user_data["awaiting_username_update"] = True


async def sync_telegram_data_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle sync telegram data command."""
    query = update.callback_query
    if not query:
        return

    await query.answer("Syncing data from Telegram...")
    user = query.from_user

    try:
        api_url = context.bot_data.get("api_url", "http://localhost:8000")
        api_key = context.bot_data.get("api_key", "dev-bot-api-key-change-in-production")

        # Update user data with current Telegram info
        update_data = {
            "telegram_username": user.username,
            "telegram_first_name": user.first_name,
            "telegram_last_name": user.last_name,
        }

        async with httpx.AsyncClient() as client:
            headers = {"X-API-Key": api_key}
            response = await client.put(
                f"{api_url}/api/v1/user/profile/{user.id}",
                json=update_data,
                headers=headers,
                timeout=10.0,
            )

            if response.status_code == 200:
                await query.answer("✅ Profile synced successfully!", show_alert=True)
                # Return to profile view to show updated data
                await profile_command(update, context)
            else:
                await query.answer("❌ Failed to sync profile", show_alert=True)

    except Exception as e:
        logger.error(f"Error syncing telegram data: {e}")
        await query.answer("❌ An error occurred", show_alert=True)


async def handle_username_update(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle username update text input."""
    if not update.message or not update.message.text:
        return

    user = update.effective_user
    if not user:
        return

    # Check if user is in username update state
    if not context.user_data or not context.user_data.get("awaiting_username_update"):
        return

    # Clear the state
    if context.user_data:
        context.user_data.pop("awaiting_username_update", None)

    new_username = update.message.text.strip()

    # Validate username
    if not new_username or len(new_username) < 3 or len(new_username) > 32:
        await update.message.reply_text(
            format_error_message("Invalid username. Must be 3-32 characters long."),
            parse_mode=ParseMode.HTML,
        )
        return

    # Remove @ if user included it
    if new_username.startswith("@"):
        new_username = new_username[1:]

    # Check for valid characters (letters, numbers, underscores)
    import re

    if not re.match(r"^[a-zA-Z0-9_]+$", new_username):
        await update.message.reply_text(
            format_error_message(
                "Invalid username. Only letters, numbers, and underscores allowed."
            ),
            parse_mode=ParseMode.HTML,
        )
        return

    try:
        api_url = context.bot_data.get("api_url", "http://localhost:8000")
        api_key = context.bot_data.get("api_key", "dev-bot-api-key-change-in-production")

        # Update username via API
        update_data = {"telegram_username": new_username}

        async with httpx.AsyncClient() as client:
            headers = {"X-API-Key": api_key}
            response = await client.put(
                f"{api_url}/api/v1/user/profile/{user.id}",
                json=update_data,
                headers=headers,
                timeout=10.0,
            )

            if response.status_code == 200:
                await update.message.reply_text(
                    f"✅ <b>Username Updated!</b>\n\n"
                    f"Your username has been changed to: "
                    f"@{escape_html(new_username)}\n\n"
                    f"Use /profile to view your updated profile.",
                    parse_mode=ParseMode.HTML,
                )
            else:
                error_data = response.json() if response.status_code != 500 else {}
                error_message = error_data.get("detail", "Unknown error occurred")
                await update.message.reply_text(
                    format_error_message(f"Failed to update username: {error_message}"),
                    parse_mode=ParseMode.HTML,
                )

    except Exception as e:
        logger.error(f"Error updating username: {e}")
        await update.message.reply_text(
            format_error_message("An error occurred while updating your username."),
            parse_mode=ParseMode.HTML,
        )
