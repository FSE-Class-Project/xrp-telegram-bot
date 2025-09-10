"""Telegram HTML formatting utilities for safe and consistent message formatting."""

import html
from decimal import Decimal
from typing import Optional, Union
from datetime import datetime


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


def format_xrp_amount(amount: Union[Decimal, float, str], decimals: int = 6) -> str:
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
    
    return format(amount, f".{decimals}f")


def format_usd_amount(amount: Union[Decimal, float, str]) -> str:
    """
    Format USD amount with proper currency formatting.
    
    Args:
        amount: USD amount to format
        
    Returns:
        Formatted USD string
    """
    if isinstance(amount, str):
        amount = Decimal(amount)
    elif isinstance(amount, float):
        amount = Decimal(str(amount))
    
    return f"${amount:,.2f}"


def format_hash(tx_hash: str, length: int = 10) -> str:
    """
    Format transaction hash for display (truncated with ellipsis).
    
    Args:
        tx_hash: Transaction hash
        length: Length of truncated hash (default: 10)
        
    Returns:
        Formatted hash string with HTML escaping
    """
    if not tx_hash or tx_hash == 'N/A':
        return escape_html('N/A')
    
    if len(tx_hash) <= length:
        return f"<code>{escape_html(tx_hash)}</code>"
    
    return f"<code>{escape_html(tx_hash[:length])}...</code>"


def format_username(username: Optional[str]) -> str:
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
    return f"❌ <b>Error</b>\n\n<code>{escape_html(error)}</code>"


def format_success_message(title: str, message: str) -> str:
    """
    Format success message for display in Telegram.
    
    Args:
        title: Success title
        message: Success message
        
    Returns:
        Formatted success message
    """
    return f"✅ <b>{escape_html(title)}</b>\n\n{message}"


def format_warning_message(title: str, message: str) -> str:
    """
    Format warning message for display in Telegram.
    
    Args:
        title: Warning title
        message: Warning message
        
    Returns:
        Formatted warning message
    """
    return f"⚠️ <b>{escape_html(title)}</b>\n\n{message}"


def format_balance_info(
    address: str, 
    balance: Union[Decimal, float, str], 
    available: Union[Decimal, float, str],
    usd_value: Union[Decimal, float, str],
    last_updated: Optional[datetime] = None
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
    formatted_usd = format_usd_amount(usd_value)
    
    message = (
        f"💰 <b>Your Balance</b>\n\n"
        f"📬 <b>Address:</b> {formatted_address}\n"
        f"💵 <b>Balance:</b> {formatted_balance} XRP\n"
        f"💸 <b>Available:</b> {formatted_available} XRP\n"
        f"📈 <b>USD Value:</b> {formatted_usd}\n\n"
    )
    
    if last_updated:
        timestamp = last_updated.strftime('%Y-%m-%d %H:%M:%S UTC')
        message += f"<i>Last updated: {timestamp}</i>"
    else:
        message += f"<i>Last updated: {datetime.utcnow().strftime('%Y-%m-%d %H:%M:%S UTC')}</i>"
    
    return message


def format_transaction_confirmation(
    recipient: str, 
    amount: Union[Decimal, float, str], 
    fee: Union[Decimal, float, str]
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
        f"📤 <b>Confirm Transaction</b>\n\n"
        f"<b>To:</b> {formatted_recipient}\n"
        f"<b>Amount:</b> {formatted_amount} XRP\n"
        f"<b>Fee:</b> {formatted_fee} XRP\n"
        f"<b>Total:</b> {formatted_total} XRP\n\n"
        f"⚠️ <i>Please review carefully.</i>\n\n"
        f"Reply <b>YES</b> to confirm or <b>NO</b> to cancel."
    )


def format_transaction_success(tx_hash: str, explorer_url: Optional[str] = None) -> str:
    """
    Format successful transaction message.
    
    Args:
        tx_hash: Transaction hash
        explorer_url: Optional explorer URL
        
    Returns:
        Formatted success message
    """
    message = (
        f"✅ <b>Transaction Successful!</b>\n\n"
        f"<b>Hash:</b> {format_hash(tx_hash)}\n\n"
    )
    
    if explorer_url:
        message += f'<a href="{escape_html(explorer_url)}">View on Explorer</a>'
    
    return message


def format_funding_instructions(balance: Union[Decimal, float, str], is_mainnet: bool = False) -> str:
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
                f"\n\n⚠️ <b>Wallet Needs Activation</b>\n"
                f"Your wallet needs at least 20 XRP to activate and transact.\n\n"
                f"<b>To fund your wallet:</b>\n"
                f"1. Copy your address above\n"
                f"2. Buy XRP from an exchange (Coinbase, Binance, etc.)\n"
                f"3. Send XRP to your address\n"
                f"4. Check balance again after confirmation\n\n"
                f"<i>💡 Minimum purchase usually covers activation costs.</i>"
            )
        else:
            return (
                f"\n\n⚠️ <b>Wallet Needs Activation</b>\n"
                f"Your wallet needs at least 20 XRP to activate and transact.\n\n"
                f"<b>To fund your wallet:</b>\n"
                f"1. Copy your address above\n"
                f"2. Visit: <a href='https://xrpl.org/xrp-testnet-faucet.html'>XRPL Testnet Faucet</a>\n"
                f"3. Paste your address and request 1000 TestNet XRP\n"
                f"4. Check balance again in 5-10 seconds\n\n"
                f"<i>💡 On mainnet, you'd buy XRP from an exchange instead.</i>"
            )
    elif balance_decimal < Decimal("25"):  # Low balance warning
        if is_mainnet:
            available_amount = format_xrp_amount(balance_decimal - Decimal('10'))
            return (
                f"\n\n💡 <b>Low Balance Notice</b>\n"
                f"You have {available_amount} XRP available for transactions.\n"
                f"Consider buying more XRP for larger transactions.\n\n"
                f"<i>💡 Buy XRP from exchanges like Coinbase or Binance.</i>"
            )
        else:
            available_amount = format_xrp_amount(balance_decimal - Decimal('10'))
            return (
                f"\n\n💡 <b>Low Balance Notice</b>\n"
                f"You have {available_amount} XRP available for transactions.\n"
                f"Consider adding more funds for larger transactions.\n\n"
                f"<b>Get more TestNet XRP:</b>\n"
                f"<a href='https://xrpl.org/xrp-testnet-faucet.html'>XRPL Testnet Faucet</a>\n\n"
                f"<i>💡 On mainnet, you'd buy XRP from an exchange.</i>"
            )
    
    return ""  # No funding message needed