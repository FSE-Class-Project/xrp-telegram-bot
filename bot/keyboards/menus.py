# Telegram keyboard layouts
# bot/keyboards/menus.py
from telegram import InlineKeyboardButton, InlineKeyboardMarkup


class Keyboards:
    """Enhanced keyboard layouts for the XRP Telegram bot."""

    def main_menu(self) -> InlineKeyboardMarkup:
        """Return the main menu keyboard."""
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
        """Return a menu for the wallet/balance view."""
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh Balance", callback_data="refresh_balance"),
                InlineKeyboardButton("📤 Send XRP", callback_data="send"),
            ],
            [
                InlineKeyboardButton("📊 Price", callback_data="price"),
                InlineKeyboardButton("📜 History", callback_data="history"),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="back"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def send_confirmation_menu(self) -> InlineKeyboardMarkup:
        """Return confirmation menu for transactions."""
        keyboard = [
            [
                InlineKeyboardButton("✅ Confirm", callback_data="confirm_send"),
                InlineKeyboardButton("❌ Cancel", callback_data="cancel_send"),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="back"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def transaction_result_menu(self) -> InlineKeyboardMarkup:
        """Return menu after transaction completion."""
        keyboard = [
            [
                InlineKeyboardButton("💰 Check Balance", callback_data="balance"),
                InlineKeyboardButton("📜 History", callback_data="history"),
            ],
            [
                InlineKeyboardButton("📤 Send Again", callback_data="send"),
                InlineKeyboardButton("🔙 Back", callback_data="back"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def price_menu(self) -> InlineKeyboardMarkup:
        """Return menu for price view."""
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="refresh_price"),
                InlineKeyboardButton("📈 Market Stats", callback_data="market_stats:30D"),
            ],
            [
                InlineKeyboardButton("💰 Balance", callback_data="balance"),
                InlineKeyboardButton("📤 Send XRP", callback_data="send"),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="back"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def heatmap_menu(self, active_timeframe: str = "30D") -> InlineKeyboardMarkup:
        """Return timeframe selector for price heatmap view."""
        active = (active_timeframe or "").upper()

        def label(tf: str) -> str:
            return f"• {tf}" if tf == active else tf

        keyboard = [
            [
                InlineKeyboardButton(label("1D"), callback_data="market_stats:1D"),
                InlineKeyboardButton(label("7D"), callback_data="market_stats:7D"),
                InlineKeyboardButton(label("30D"), callback_data="market_stats:30D"),
            ],
            [
                InlineKeyboardButton(label("90D"), callback_data="market_stats:90D"),
                InlineKeyboardButton(label("1Y"), callback_data="market_stats:1Y"),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="back"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def history_menu(self) -> InlineKeyboardMarkup:
        """Return menu for transaction history."""
        keyboard = [
            [
                InlineKeyboardButton("🔄 Refresh", callback_data="refresh_history"),
                InlineKeyboardButton("💰 Balance", callback_data="balance"),
            ],
            [
                InlineKeyboardButton("📤 Send XRP", callback_data="send"),
                InlineKeyboardButton("🔙 Back", callback_data="back"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def profile_menu(self) -> InlineKeyboardMarkup:
        """Return menu for profile view."""
        keyboard = [
            [
                InlineKeyboardButton("💰 Balance", callback_data="balance"),
                InlineKeyboardButton("⚙️ Settings", callback_data="settings"),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="back"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def error_menu(self) -> InlineKeyboardMarkup:
        """Return menu for error messages."""
        keyboard = [
            [
                InlineKeyboardButton("🔄 Try Again", callback_data="retry"),
                InlineKeyboardButton("❓ Help", callback_data="help"),
            ],
            [
                InlineKeyboardButton("🔙 Back", callback_data="back"),
                InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"),
            ],
        ]
        return InlineKeyboardMarkup(keyboard)

    def back_to_main(self) -> InlineKeyboardMarkup:
        """Create simple back to main menu keyboard."""
        return InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("🔙 Back", callback_data="back"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu"),
                ]
            ]
        )


# Create a single instance of the Keyboards class to be imported elsewhere
keyboards = Keyboards()
