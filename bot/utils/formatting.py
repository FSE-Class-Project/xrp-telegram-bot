"""Telegram HTML formatting utilities for safe and consistent message formatting."""

import html
from datetime import datetime
from decimal import Decimal


def escape_html(text: str) -> str:
    """
    Safely escape HTML characters for Telegram HTML parsing.

    Args:
        text: Text to escape

    Returns:
        HTML-safe text
    """
    return html.escape(str(text))


def format_xrp_address(address: str) -> str:
    """
    Format XRP address with safe HTML escaping and code styling.

    Args:
        address: XRP address to format

    Returns:
        Formatted HTML string
    """
    return f"<code>{escape_html(address)}</code>"


def format_xrp_amount(amount: Decimal | float | str, decimals: int = 6) -> str:
    """
    Format XRP amount with consistent decimal places.

    Args:
        amount: XRP amount to format
        decimals: Number of decimal places (default: 6)

    Returns:
        Formatted amount string
    """
    if isinstance(amount, str):
        amount = Decimal(amount)
    elif isinstance(amount, float):
        amount = Decimal(str(amount))

    format_spec = f".{decimals}f"
    return format(amount, format_spec)


def format_currency_amount(amount: Decimal | float | str, currency: str = "USD") -> str:
    """
    Format an amount with currency symbol or unit (supports fiat + crypto).

    - Fiat: USD, EUR, GBP, ZAR, JPY → symbol prefix with 2 decimals
    - Crypto: BTC (8 decimals), ETH (6 decimals) with unit suffix

    Args:
        amount: Numeric amount
        currency: Currency code

    Returns:
        Formatted string with currency notation
    """
    if isinstance(amount, str):
        amount = Decimal(amount)
    elif isinstance(amount, float):
        amount = Decimal(str(amount))

    c = currency.upper()
    if c in {"BTC", "ETH"}:
        decimals = 8 if c == "BTC" else 6
        fmt = f".{decimals}f"
        return f"{format(amount, fmt)} {c}"

    symbols = {
        "USD": "$",
        "EUR": "€",
        "GBP": "£",
        "ZAR": "R",
        "JPY": "¥",
    }
    symbol = symbols.get(c, "$")
    return f"{symbol}{amount:,.2f}"


def format_hash(tx_hash: str, length: int = 10) -> str:
    """
    Format transaction hash for display (truncated with ellipsis).

    Args:
        tx_hash: Transaction hash
        length: Length of truncated hash (default: 10)

    Returns:
        Formatted hash string with HTML escaping
    """
    if not tx_hash or tx_hash == "N/A":
        return escape_html("N/A")

    if len(tx_hash) <= length:
        return f"<code>{escape_html(tx_hash)}</code>"

    return f"<code>{escape_html(tx_hash[:length])}...</code>"


def format_username(username: str | None) -> str:
    """
    Format Telegram username with safe escaping.

    Args:
        username: Telegram username (without @)

    Returns:
        Formatted username string
    """
    if not username:
        return "Not set"

    return f"@{escape_html(username)}"


def format_error_message(error: str) -> str:
    """
    Format error message for display in Telegram.

    Args:
        error: Error message

    Returns:
        Formatted error message
    """
    # Safely escape and format the error message to prevent f-string conflicts
    escaped_error = escape_html(str(error))
    return "❌ <b>Error</b>\n\n<code>" + escaped_error + "</code>"


def format_success_message(title: str, message: str) -> str:
    """
    Format success message for display in Telegram.

    Args:
        title: Success title
        message: Success message

    Returns:
        Formatted success message
    """
    # Safely escape title to prevent formatting conflicts
    escaped_title = escape_html(str(title))
    return "✅ <b>" + escaped_title + "</b>\n\n" + message


def format_warning_message(title: str, message: str) -> str:
    """
    Format warning message for display in Telegram.

    Args:
        title: Warning title
        message: Warning message

    Returns:
        Formatted warning message
    """
    # Safely escape title to prevent formatting conflicts
    escaped_title = escape_html(str(title))
    return "⚠️ <b>" + escaped_title + "</b>\n\n" + message


def format_balance_info(
    address: str,
    balance: Decimal | float | str,
    available: Decimal | float | str,
    fiat_value: Decimal | float | str,
    fiat_currency: str = "USD",
    last_updated: datetime | None = None,
) -> str:
    """
    Format balance information with consistent styling.

    Args:
        address: XRP address
        balance: Total balance
        available: Available balance
        usd_value: USD value
        last_updated: Last update timestamp

    Returns:
        Formatted balance message
    """
    formatted_address = format_xrp_address(address)
    formatted_balance = format_xrp_amount(balance)
    formatted_available = format_xrp_amount(available)
    formatted_fiat = format_currency_amount(fiat_value, fiat_currency)

    message = (
        "💰 <b>Your Balance</b>\n\n"
        "📬 <b>Address:</b> " + formatted_address + "\n"
        "💵 <b>Balance:</b> " + formatted_balance + " XRP\n"
        "💸 <b>Available:</b> " + formatted_available + " XRP\n"
        "📈 <b>Value:</b> " + formatted_fiat + "\n\n"
    )

    if last_updated:
        timestamp = last_updated.strftime("%Y-%m-%d %H:%M:%S UTC")
        message += "<i>Last updated: " + timestamp + "</i>"
    else:
        timestamp = datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S UTC")
        message += "<i>Last updated: " + timestamp + "</i>"

    return message


def format_transaction_confirmation(
    recipient: str, amount: Decimal | float | str, fee: Decimal | float | str
) -> str:
    """
    Format transaction confirmation message.

    Args:
        recipient: Recipient address
        amount: Transaction amount
        fee: Transaction fee

    Returns:
        Formatted confirmation message
    """
    total = Decimal(str(amount)) + Decimal(str(fee))

    formatted_recipient = format_xrp_address(recipient)
    formatted_amount = format_xrp_amount(amount)
    formatted_fee = format_xrp_amount(fee)
    formatted_total = format_xrp_amount(total)

    return (
        "📤 <b>Confirm Transaction</b>\n\n"
        "<b>To:</b> " + formatted_recipient + "\n"
        "<b>Amount:</b> " + formatted_amount + " XRP\n"
        "<b>Fee:</b> " + formatted_fee + " XRP\n"
        "<b>Total:</b> " + formatted_total + " XRP\n\n"
        "⚠️ <i>Please review carefully.</i>\n\n"
        "Reply <b>YES</b> to confirm or <b>NO</b> to cancel."
    )


def format_transaction_success(tx_hash: str, explorer_url: str | None = None) -> str:
    """
    Format successful transaction message.

    Args:
        tx_hash: Transaction hash
        explorer_url: Optional explorer URL

    Returns:
        Formatted success message
    """
    message = (
        "✅ <b>Transaction Successful!</b>\n\n" "<b>Hash:</b> " + format_hash(tx_hash) + "\n\n"
    )

    if explorer_url:
        message += '<a href="' + escape_html(explorer_url) + '">View on Explorer</a>'

    return message


def format_funding_instructions(balance: Decimal | float | str, is_mainnet: bool = False) -> str:
    """
    Format funding instructions based on current balance and network.

    Args:
        balance: Current balance
        is_mainnet: Whether this is mainnet (default: False for testnet)

    Returns:
        Formatted funding instructions
    """
    balance_decimal = Decimal(str(balance))

    if balance_decimal < Decimal("20"):  # Below minimum reserve
        if is_mainnet:
            return (
                "\n\n⚠️ <b>Wallet Needs Activation</b>\n"
                "Your wallet needs at least 20 XRP to activate and transact.\n\n"
                "<b>To fund your wallet:</b>\n"
                "1. Copy your address above\n"
                "2. Buy XRP from an exchange (Coinbase, Binance, etc.)\n"
                "3. Send XRP to your address\n"
                "4. Check balance again after confirmation\n\n"
                "<i>💡 Minimum purchase usually covers activation costs.</i>"
            )
        else:
            return (
                "\n\n⚠️ <b>Wallet Needs Activation</b>\n"
                "Your wallet needs at least 20 XRP to activate and transact.\n\n"
                "<b>To fund your wallet:</b>\n"
                "1. Copy your address above\n"
                "2. Visit: <a href='https://xrpl.org/xrp-testnet-faucet.html'>XRPL Testnet Faucet</a>\n"
                "3. Paste your address and request 1000 TestNet XRP\n"
                "4. Check balance again in 5-10 seconds\n\n"
                "<i>💡 On mainnet, you'd buy XRP from an exchange instead.</i>"
            )
    elif balance_decimal < Decimal("25"):  # Low balance warning
        if is_mainnet:
            available_amount = format_xrp_amount(balance_decimal - Decimal("10"))
            return (
                "\n\n💡 <b>Low Balance Notice</b>\n"
                "You have " + available_amount + " XRP available for transactions.\n"
                "Consider buying more XRP for larger transactions.\n\n"
                "<i>💡 Buy XRP from exchanges like Coinbase or Binance.</i>"
            )
        else:
            available_amount = format_xrp_amount(balance_decimal - Decimal("10"))
            return (
                "\n\n💡 <b>Low Balance Notice</b>\n"
                "You have " + available_amount + " XRP available for transactions.\n"
                "Consider adding more funds for larger transactions.\n\n"
                "<b>Get more TestNet XRP:</b>\n"
                "<a href='https://xrpl.org/xrp-testnet-faucet.html'>XRPL Testnet Faucet</a>\n\n"
                "<i>💡 On mainnet, you'd buy XRP from an exchange.</i>"
            )

    return ""  # No funding message needed
