# Message templates for bot responses
from __future__ import annotations
from typing import Optional, Literal

# Language type
Lang = Literal["en"]

# App branding
class AppBrand:
    app_name: str = "XRPay TG"
    org_name: str = "UCT FinHub"
    asset_code: str = "XRP"
    fiat_code: str = "USD"
    explorer_base_url: str = "https://testnet.xrpl.org/transactions"

BRAND = AppBrand()

# English message templates
EN: dict[str, object] = {
    "app.tagline": "Fast, simple XRP payments inside Telegram.",
    "app.wip": "⚙️ This feature is coming soon.",
    "error.generic": "⚠️ Oops, something went wrong. Please try again.",
    "error.not_authorized": "🚫 You are not authorized to use this command.",
    "error.rate_limited": "⏳ You are sending requests too quickly. Please slow down.",
    "cmd.unknown": "🤖 I don't recognize that command. Try /help.",

    # Onboarding
    "welcome": lambda username=None: (
        f"👋 Welcome{f', {username}' if username else ''} to {BRAND.app_name}!\n\n"
        "With this bot you can:\n"
        "• Generate a custodial XRPL account (Testnet)\n"
        "• Check your XRP balance\n"
        "• Send XRP to other users\n"
        "• View transaction history\n"
        "• Get real-time XRP prices\n\n"
        "🚀 **Getting Started:**\n"
        "1. Use /profile to create your XRPL account\n"
        "2. Use /balance to check your XRP balance\n"
        "3. Use /help to see all available commands\n\n"
        f"*Powered by {BRAND.org_name}*"
    ),

    "help": (
        "🤖 **XRPay TG Bot Commands**\n\n"
        "**Account Management:**\n"
        "• /profile - View or create your XRPL account\n"
        "• /balance - Check your XRP balance\n\n"
        "**Transactions:**\n"
        "• /send - Send XRP to another user\n"
        "• /history - View your transaction history\n"
        "• /cancel - Stop outgoing transactions\n\n"
        "**Market Data:**\n"
        "• /price - Get current XRP price\n\n"
        "**General:**\n"
        "• /start - Welcome message\n"
        "• /help - Show this help\n"
        "• /clear - Clear chat data\n\n"
        "🔗 **Network:** XRPL Testnet\n"
        f"🌐 **Explorer:** {BRAND.explorer_base_url}\n\n"
        f"*Powered by {BRAND.org_name}*"
    ),

    "signup.ok": lambda addr: (
        f"✅ **Account Created Successfully!**\n\n"
        f"**Your XRPL Address:**\n"
        f"`{addr}`\n\n"
        "🔐 **Important:** This is a custodial account. "
        "Your private keys are securely managed by the bot.\n\n"
        "💰 **Next Steps:**\n"
        "• Use /balance to check your balance\n"
        "• Use /send to transfer XRP\n"
        "• Use /help for more commands"
    ),

    "signup.funded": lambda amount: (
        f"🎉 **Account Funded!**\n\n"
        f"You've received **{amount} XRP** from the testnet faucet!\n\n"
        "You can now:\n"
        "• Check your balance with /balance\n"
        "• Send XRP with /send\n"
        "• View your profile with /profile"
    ),

    "me": lambda username, addr, created_at: (
        f" **Your Profile**\n\n"
        f"**Username:** {username or 'Not set'}\n"
        f"**XRPL Address:** `{addr}`\n"
        f"**Account Created:** {created_at}\n\n"
        "**Quick Actions:**\n"
        "• /balance - Check balance\n"
        "• /send - Send XRP\n"
        "• /history - View transactions"
    ),

    "balance": lambda xrp_amount, fiat_amount=None: (
        f" **Your XRP Balance**\n\n"
        f"**XRP:** {xrp_amount} XRP\n"
        f"{f'**USD:** ${fiat_amount:.2f}' if fiat_amount else ''}\n\n"
        "**Quick Actions:**\n"
        "• /send - Send XRP\n"
        "• /history - View transactions"
    ),

    "send.howto": (
        "💸 **How to Send XRP**\n\n"
        "**Format:** `/send <amount> <recipient>`\n\n"
        "**Examples:**\n"
        "• `/send 10 rN7n7otQDd6FczFgLdSqtcsAUxDkw6fzRH`\n"
        "• `/send 5.5 @username`\n\n"
        "**Notes:**\n"
        "• Amount can be decimal (e.g., 10.5)\n"
        "• Recipient can be XRPL address or Telegram username\n"
        "• Minimum amount: 0.000001 XRP"
    ),

    "send.confirm": lambda sender_addr, recipient_disp, amount, memo=None: (
        f"📋 **Confirm Transaction**\n\n"
        f"**From:** `{sender_addr}`\n"
        f"**To:** {recipient_disp}\n"
        f"**Amount:** {amount} XRP\n"
        f"{f'**Memo:** {memo}' if memo else ''}\n\n"
        "⚠️ **Please confirm this transaction is correct.**\n"
        "Reply with 'yes' to proceed or 'no' to cancel."
    ),

    "send.processing": (
        "⏳ **Processing Transaction...**\n\n"
        "Please wait while we process your XRP transfer.\n"
        "This usually takes a few seconds."
    ),

    "send.ok": lambda amount, to_disp, tx_hash=None: (
        f"✅ **Transaction Successful!**\n\n"
        f"**Amount:** {amount} XRP\n"
        f"**To:** {to_disp}\n"
        f"{f'**Transaction Hash:** `{tx_hash}`' if tx_hash else ''}\n\n"
        "Your transaction has been confirmed on the XRPL network."
    ),

    "send.failed": lambda reason=None: (
        f"❌ **Transaction Failed**\n\n"
        f"{f'**Reason:** {reason}' if reason else 'An error occurred while processing your transaction.'}\n\n"
        "Please try again or contact support if the problem persists."
    ),

    "price.now": lambda price_usd, ts=None: (
        f"📈 **Current XRP Price**\n\n"
        f"**Price:** ${price_usd:.4f} USD\n"
        f"{f'**Updated:** {ts}' if ts else ''}\n\n"
        "💡 Use /price for real-time updates"
    ),

    "price.history.header": (
        "📊 **XRP Price History**\n\n"
        "Recent price movements:"
    ),

    "price.history.item": lambda ts, px: (
        f"• {ts}: ${px:.4f} USD"
    ),

    "history.header": (
        "📋 **Transaction History**\n\n"
        "Your recent XRP transactions:"
    ),

    "history.empty": (
        "📋 **Transaction History**\n\n"
        "No transactions found.\n\n"
        "Start by sending some XRP with /send!"
    ),

    "history.item": lambda created_at, amount, to_addr, status, tx_hash=None: (
        f"**{created_at}**\n"
        f"• Amount: {amount} XRP\n"
        f"• To: `{to_addr}`\n"
        f"• Status: {status}\n"
        f"{f'• Hash: `{tx_hash}`' if tx_hash else ''}\n"
    ),

    "admin.health": lambda db_ok, xrpl_ok, webhook_ok: (
        f" **System Health**\n\n"
        f"**Database:** {'✅ OK' if db_ok else '❌ Error'}\n"
        f"**XRPL Connection:** {'✅ OK' if xrpl_ok else '❌ Error'}\n"
        f"**Webhook:** {'✅ OK' if webhook_ok else '❌ Error'}"
    ),

    # New commands
    "cancel": (
        "❌ **Transaction Cancelled**\n\n"
        "Any outgoing transactions have been stopped.\n"
        "Your transaction queue has been cleared.\n\n"
        "You can now start a new transaction or use other commands.\n"
        "Use /help to see available commands."
    ),

    "clear": (
        "🧹 **Chat Data Cleared**\n\n"
        "All conversation data and temporary information has been cleared.\n"
        "Your account data remains safe.\n\n"
        "You can now start fresh with any command.\n"
        "Use /help to see available commands."
    ),
}

# Registry of languages
_LANGS: dict[Lang, dict[str, object]] = {
    "en": EN,
}

def t(key: str, lang: Lang = "en", /, **kwargs) -> str:
    """
    Resolve a template by key and render it with kwargs.
    - If the value is a callable, we call it with kwargs.
    - If it's a simple string, we format() with kwargs (if any).
    """
    bundle = _LANGS.get(lang, EN)
    if key not in bundle:
        # Fallback
        return f"[missing string: {key}]"

    val = bundle[key]
    if callable(val):
        return val(**kwargs)
    if kwargs:
        try:
            return str(val).format(**kwargs)
        except Exception:
            # If formatting fails due to missing keys, return raw
            return str(val)
    return str(val)

# Convenience wrappers for commonly-used messages (keeps call sites clean)
def welcome(username: Optional[str] = None, lang: Lang = "en") -> str:
    return t("welcome", lang, username=username)

def help_text(lang: Lang = "en") -> str:
    return t("help", lang)

def signup_ok(addr: str, lang: Lang = "en") -> str:
    return t("signup.ok", lang, addr=addr)

def signup_funded(amount_xrp: float, lang: Lang = "en") -> str:
    return t("signup.funded", lang, amount=amount_xrp)

def me_profile(username: Optional[str], addr: str, created_at_iso: str, lang: Lang = "en") -> str:
    return t("me", lang, username=username, addr=addr, created_at=created_at_iso)

def balance_text(xrp_amount: float, fiat_amount: Optional[float] = None, lang: Lang = "en") -> str:
    return t("balance", lang, xrp_amount=xrp_amount, fiat_amount=fiat_amount)

def send_howto(lang: Lang = "en") -> str:
    return t("send.howto", lang)

def send_confirm(sender_addr: str, recipient_display: str, amount_xrp: float, memo: Optional[str] = None,
                 lang: Lang = "en") -> str:
    return t(
        "send.confirm",
        lang,
        sender_addr=sender_addr,
        recipient_disp=recipient_display,
        amount=amount_xrp,
        memo=memo
    )

def send_processing(lang: Lang = "en") -> str:
    return t("send.processing", lang)

def send_ok(amount_xrp: float, recipient_display: str, tx_hash: Optional[str] = None,
            lang: Lang = "en") -> str:
    return t("send.ok", lang, amount=amount_xrp, to_disp=recipient_display, tx_hash=tx_hash)

def send_failed(reason: Optional[str] = None, lang: Lang = "en") -> str:
    return t("send.failed", lang, reason=reason)

def price_now(price_usd: float, ts_iso: Optional[str] = None, lang: Lang = "en") -> str:
    return t("price.now", lang, price_usd=price_usd, ts=ts_iso)

def price_history_header(lang: Lang = "en") -> str:
    return t("price.history.header", lang)

def price_history_item(ts_iso: str, price_usd: float, lang: Lang = "en") -> str:
    return t("price.history.item", lang, ts=ts_iso, px=price_usd)

def history_header(lang: Lang = "en") -> str:
    return t("history.header", lang)

def history_empty(lang: Lang = "en") -> str:
    return t("history.empty", lang)

def history_item(created_at_iso: str, amount_xrp: float, to_addr: str,
                 status: Literal["pending", "confirmed", "failed"], tx_hash: Optional[str] = None,
                 lang: Lang = "en") -> str:
    return t(
        "history.item",
        lang,
        created_at=created_at_iso,
        amount=amount_xrp,
        to_addr=to_addr,
        status=status,
        tx_hash=tx_hash
    )

def admin_health(db_ok: bool, xrpl_ok: bool, webhook_ok: bool, lang: Lang = "en") -> str:
    return t("admin.health", lang, db_ok=db_ok, xrpl_ok=xrpl_ok, webhook_ok=webhook_ok)

# New command convenience wrappers
def cancel_text(lang: Lang = "en") -> str:
    return t("cancel", lang)

def clear_text(lang: Lang = "en") -> str:
    return t("clear", lang)
