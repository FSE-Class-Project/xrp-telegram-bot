# bot/handlers/settings.py
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


async def settings_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /settings command and settings menu navigation."""
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
        # Get current user settings from API
        api_url = context.bot_data.get('api_url', 'http://localhost:8000')
        api_key = context.bot_data.get('api_key', 'dev-bot-api-key-change-in-production')
        
        settings_data = await fetch_user_settings(api_url, api_key, user_id)
        
        if settings_data:
            message = format_settings_menu(settings_data)
            keyboard = create_settings_keyboard()
            
            await reply_func(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        else:
            await reply_func(
                format_error_message(
                    "Settings Unavailable",
                    "Could not load your settings. Please try again later."
                ),
                parse_mode=ParseMode.HTML
            )
            
    except Exception as e:
        logger.error(f"Error in settings_command: {e}", exc_info=True)
        await reply_func(
            format_error_message(
                "Settings Error",
                "An error occurred while loading settings."
            ),
            parse_mode=ParseMode.HTML
        )


async def notification_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle notification settings."""
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    user_id = query.from_user.id
    
    try:
        api_url = context.bot_data.get('api_url', 'http://localhost:8000')
        api_key = context.bot_data.get('api_key', 'dev-bot-api-key-change-in-production')
        
        settings_data = await fetch_user_settings(api_url, api_key, user_id)
        
        if settings_data:
            price_alerts = settings_data.get('price_alerts', False)
            tx_notifications = settings_data.get('transaction_notifications', True)
            
            message = f"""
📲 <b>Notification Settings</b>

<b>Current Settings:</b>
📊 Price Alerts: {'✅ Enabled' if price_alerts else '❌ Disabled'}
💸 Transaction Notifications: {'✅ Enabled' if tx_notifications else '❌ Disabled'}

<i>Configure what notifications you want to receive from the bot.</i>
"""
            
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        f"📊 Price Alerts: {'✅' if price_alerts else '❌'}",
                        callback_data=f"toggle_price_alerts"
                    )
                ],
                [
                    InlineKeyboardButton(
                        f"💸 Transactions: {'✅' if tx_notifications else '❌'}",
                        callback_data=f"toggle_tx_notifications"
                    )
                ],
                [
                    InlineKeyboardButton("🔙 Back to Settings", callback_data="settings"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
                ]
            ])
            
            await query.message.edit_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        else:
            await query.answer("Could not load notification settings", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in notification_settings: {e}")
        await query.answer("An error occurred", show_alert=True)


async def currency_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle currency display settings."""
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    user_id = query.from_user.id
    
    try:
        api_url = context.bot_data.get('api_url', 'http://localhost:8000')
        api_key = context.bot_data.get('api_key', 'dev-bot-api-key-change-in-production')
        
        settings_data = await fetch_user_settings(api_url, api_key, user_id)
        
        if settings_data:
            current_currency = settings_data.get('currency_display', 'USD')
            
            message = f"""
💱 <b>Currency Settings</b>

<b>Current Display Currency:</b> {current_currency}

Select your preferred currency for displaying XRP values:
"""
            
            # Available currencies
            currencies = ['USD', 'EUR', 'GBP', 'JPY', 'BTC', 'ETH']
            keyboard = []
            
            # Create rows of 2 currencies each
            for i in range(0, len(currencies), 2):
                row = []
                for j in range(2):
                    if i + j < len(currencies):
                        currency = currencies[i + j]
                        prefix = "✅ " if currency == current_currency else ""
                        row.append(InlineKeyboardButton(
                            f"{prefix}{currency}",
                            callback_data=f"set_currency_{currency}"
                        ))
                keyboard.append(row)
            
            keyboard.extend([
                [
                    InlineKeyboardButton("🔙 Back to Settings", callback_data="settings"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
                ]
            ])
            
            await query.message.edit_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=InlineKeyboardMarkup(keyboard)
            )
        else:
            await query.answer("Could not load currency settings", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in currency_settings: {e}")
        await query.answer("An error occurred", show_alert=True)


async def security_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle security settings."""
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    user_id = query.from_user.id
    
    try:
        api_url = context.bot_data.get('api_url', 'http://localhost:8000')
        api_key = context.bot_data.get('api_key', 'dev-bot-api-key-change-in-production')
        
        settings_data = await fetch_user_settings(api_url, api_key, user_id)
        
        if settings_data:
            two_factor = settings_data.get('two_factor_enabled', False)
            has_pin = settings_data.get('pin_code') is not None
            
            message = f"""
🔐 <b>Security Settings</b>

<b>Current Security:</b>
🔢 PIN Protection: {'✅ Enabled' if has_pin else '❌ Disabled'}
🛡️ Two-Factor Auth: {'✅ Enabled' if two_factor else '❌ Disabled'}

<i>Enhance your wallet security with additional protection layers.</i>

⚠️ <b>Important:</b> These features add extra security but may slow down transactions.
"""
            
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton(
                        f"🔢 {'Change' if has_pin else 'Set'} PIN",
                        callback_data="setup_pin"
                    )
                ],
                [
                    InlineKeyboardButton(
                        f"🛡️ 2FA: {'Disable' if two_factor else 'Enable'}",
                        callback_data="toggle_2fa"
                    )
                ],
                [
                    InlineKeyboardButton("🔙 Back to Settings", callback_data="settings"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
                ]
            ])
            
            await query.message.edit_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        else:
            await query.answer("Could not load security settings", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in security_settings: {e}")
        await query.answer("An error occurred", show_alert=True)


async def toggle_setting(update: Update, context: ContextTypes.DEFAULT_TYPE, setting_name: str) -> None:
    """Toggle a boolean setting."""
    query = update.callback_query
    if not query:
        return
    
    user_id = query.from_user.id
    
    try:
        api_url = context.bot_data.get('api_url', 'http://localhost:8000')
        api_key = context.bot_data.get('api_key', 'dev-bot-api-key-change-in-production')
        
        # Update setting via API
        success = await update_user_setting(api_url, api_key, user_id, setting_name, None)
        
        if success:
            # Get updated settings
            settings_data = await fetch_user_settings(api_url, api_key, user_id)
            
            setting_value = settings_data.get(setting_name, False) if settings_data else False
            status = "enabled" if setting_value else "disabled"
            
            await query.answer(f"Setting {status} successfully!", show_alert=True)
            
            # Return to appropriate settings page
            if setting_name in ['price_alerts', 'transaction_notifications']:
                await notification_settings(update, context)
            elif setting_name == 'two_factor_enabled':
                await security_settings(update, context)
        else:
            await query.answer("Failed to update setting", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error toggling {setting_name}: {e}")
        await query.answer("An error occurred", show_alert=True)


async def set_currency(update: Update, context: ContextTypes.DEFAULT_TYPE, currency: str) -> None:
    """Set currency display preference."""
    query = update.callback_query
    if not query:
        return
    
    user_id = query.from_user.id
    
    try:
        api_url = context.bot_data.get('api_url', 'http://localhost:8000')
        api_key = context.bot_data.get('api_key', 'dev-bot-api-key-change-in-production')
        
        # Update currency setting
        success = await update_user_setting(api_url, api_key, user_id, 'currency_display', currency)
        
        if success:
            await query.answer(f"Currency set to {currency}!", show_alert=True)
            await currency_settings(update, context)
        else:
            await query.answer("Failed to update currency", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error setting currency to {currency}: {e}")
        await query.answer("An error occurred", show_alert=True)


async def fetch_user_settings(api_url: str, api_key: str, user_id: int) -> Optional[Dict[str, Any]]:
    """Fetch user settings from API."""
    try:
        async with httpx.AsyncClient() as client:
            headers = {"X-API-Key": api_key}
            response = await client.get(
                f"{api_url}/api/v1/user/settings/{user_id}",
                headers=headers,
                timeout=10.0
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Settings API returned status {response.status_code}")
                return None
                
    except Exception as e:
        logger.error(f"Error fetching user settings: {e}")
        return None


async def update_user_setting(api_url: str, api_key: str, user_id: int, setting_name: str, value: Any) -> bool:
    """Update a user setting via API."""
    try:
        async with httpx.AsyncClient() as client:
            headers = {"X-API-Key": api_key}
            
            # For toggle settings, we send a toggle request
            if value is None:
                response = await client.post(
                    f"{api_url}/api/v1/user/settings/{user_id}/toggle",
                    json={"setting": setting_name},
                    headers=headers,
                    timeout=10.0
                )
            else:
                # For value settings, we send an update request
                response = await client.put(
                    f"{api_url}/api/v1/user/settings/{user_id}",
                    json={setting_name: value},
                    headers=headers,
                    timeout=10.0
                )
            
            return response.status_code == 200
            
    except Exception as e:
        logger.error(f"Error updating setting {setting_name}: {e}")
        return False


def format_settings_menu(settings_data: Dict[str, Any]) -> str:
    """Format the main settings menu message."""
    price_alerts = settings_data.get('price_alerts', False)
    tx_notifications = settings_data.get('transaction_notifications', True)
    currency = settings_data.get('currency_display', 'USD')
    language = settings_data.get('language', 'en')
    two_factor = settings_data.get('two_factor_enabled', False)
    has_pin = settings_data.get('pin_code') is not None
    
    return f"""
⚙️ <b>Bot Settings</b>

<b>Notifications:</b>
📊 Price Alerts: {'✅' if price_alerts else '❌'}
💸 Transactions: {'✅' if tx_notifications else '❌'}

<b>Display:</b>
💱 Currency: {currency}
🌐 Language: {language.upper()}

<b>Security:</b>
🔢 PIN: {'✅' if has_pin else '❌'}
🛡️ 2FA: {'✅' if two_factor else '❌'}

<i>Customize your bot experience and security settings.</i>
"""


def create_settings_keyboard() -> InlineKeyboardMarkup:
    """Create the main settings keyboard."""
    return InlineKeyboardMarkup([
        [
            InlineKeyboardButton("📲 Notifications", callback_data="notification_settings"),
            InlineKeyboardButton("💱 Currency", callback_data="currency_settings")
        ],
        [
            InlineKeyboardButton("🔐 Security", callback_data="security_settings"),
            InlineKeyboardButton("🌐 Language", callback_data="language_settings")
        ],
        [
            InlineKeyboardButton("📊 Export Data", callback_data="export_data"),
            InlineKeyboardButton("🗑️ Delete Account", callback_data="delete_account")
        ],
        [
            InlineKeyboardButton("🔙 Back", callback_data="profile"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
        ]
    ])


async def language_settings(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle language settings (placeholder for future implementation)."""
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    message = """
🌐 <b>Language Settings</b>

<b>Current Language:</b> English

<i>Multi-language support coming soon!</i>

We're working on adding support for:
• Spanish 🇪🇸
• French 🇫🇷  
• German 🇩🇪
• Portuguese 🇵🇹
• Chinese 🇨🇳
• Japanese 🇯🇵

Stay tuned for updates!
"""
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("🔙 Back to Settings", callback_data="settings"),
            InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
        ]
    ])
    
    await query.message.edit_text(
        message,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )


async def export_data(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle data export request."""
    query = update.callback_query
    if not query:
        return
    
    await query.answer("Preparing data export...")
    user_id = query.from_user.id
    
    try:
        api_url = context.bot_data.get('api_url', 'http://localhost:8000')
        api_key = context.bot_data.get('api_key', 'dev-bot-api-key-change-in-production')
        
        # Request data export from API
        async with httpx.AsyncClient() as client:
            headers = {"X-API-Key": api_key}
            response = await client.post(
                f"{api_url}/api/v1/user/export/{user_id}",
                headers=headers,
                timeout=30.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                message = f"""
📊 <b>Data Export</b>

Your data export has been prepared:

<b>Profile:</b>
• Account created: {data.get('created_at', 'N/A')[:10]}
• Total transactions: {data.get('transaction_count', 0)}
• Total XRP sent: {data.get('total_sent', 0):.6f}
• Current balance: {data.get('current_balance', 0):.6f}

<b>Export Options:</b>
• Transaction history (CSV)
• Account settings (JSON)  
• Complete profile data (JSON)

<i>Your data is ready for download. Contact support to receive your export file.</i>
"""
                
                keyboard = InlineKeyboardMarkup([
                    [InlineKeyboardButton("📞 Contact Support", url="https://t.me/your_support_bot")],
                    [
                        InlineKeyboardButton("🔙 Back to Settings", callback_data="settings"),
                        InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
                    ]
                ])
                
                await query.message.edit_text(
                    message,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard
                )
            else:
                await query.answer("Failed to export data", show_alert=True)
                
    except Exception as e:
        logger.error(f"Error exporting data: {e}")
        await query.answer("Export failed", show_alert=True)


async def delete_account_warning(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Show account deletion warning."""
    query = update.callback_query
    if not query:
        return
    
    await query.answer()
    
    message = """
🗑️ <b>Delete Account</b>

⚠️ <b>WARNING: This action cannot be undone!</b>

Deleting your account will:
• Permanently delete your wallet and keys
• Remove all transaction history
• Cancel all pending operations
• Delete all personal data

<b>Before deleting:</b>
1. Export your data if needed
2. Transfer any remaining XRP to another wallet
3. Make sure you have your seed phrase backed up

Are you absolutely sure you want to delete your account?
"""
    
    keyboard = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("❌ Cancel", callback_data="settings"),
            InlineKeyboardButton("🗑️ Confirm Delete", callback_data="confirm_delete_account")
        ]
    ])
    
    await query.message.edit_text(
        message,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard
    )