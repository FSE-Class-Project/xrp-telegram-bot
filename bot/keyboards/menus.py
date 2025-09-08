# Telegram keyboard layouts
# bot/keyboards/menus.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup

class Keyboards:
    def main_menu(self) -> InlineKeyboardMarkup:
        """Returns the main menu keyboard."""
        keyboard = [
            [
                InlineKeyboardButton("💰 Balance", callback_data="balance"),
                InlineKeyboardButton("📤 Send", callback_data="send"),
            ],
            [
                InlineKeyboardButton("📊 Price", callback_data="price"),
                InlineKeyboardButton("📜 History", callback_data="history"),
            ],
            [
                InlineKeyboardButton("👤 Profile", callback_data="profile"),
                InlineKeyboardButton("❓ Help", callback_data="help"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def wallet_menu(self) -> InlineKeyboardMarkup:
        """Returns a menu for the wallet/balance view."""
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh Balance", callback_data="refresh_balance"),
            ],
            [
                InlineKeyboardButton("⬅️ Back to Main Menu", callback_data="main_menu"),
            ]
        ]
        return InlineKeyboardMarkup(keyboard)

# Create a single instance of the Keyboards class to be imported elsewhere
keyboards = Keyboards()
