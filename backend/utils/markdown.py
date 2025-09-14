# bot/utils/markdown.py
"""
Utility functions for handling Telegram's MarkdownV2 formatting
"""


def escape_markdown_v2(text: str, preserve_code: bool = False) -> str:
    """
    Escape special characters for Telegram's MarkdownV2 parse mode

    Args:
        text: The text to escape
        preserve_code: If True, preserves text within backticks

    Returns:
        Escaped text safe for MarkdownV2
    """
    if not text:
        return text

    # Characters that need escaping in MarkdownV2
    escape_chars = r"_*[]()~`>#+-=|{}.!"

    if preserve_code:
        # Split by backticks to preserve code blocks
        parts = text.split("`")
        escaped_parts = []

        for i, part in enumerate(parts):
            if i % 2 == 0:  # Not inside code block
                # Escape each special character
                for char in escape_chars:
                    part = part.replace(char, f"\\{char}")
                escaped_parts.append(part)
            else:  # Inside code block
                escaped_parts.append(part)

        # Rejoin with backticks
        return "`".join(escaped_parts)
    else:
        # Escape all special characters
        escaped = text
        for char in escape_chars:
            escaped = escaped.replace(char, f"\\{char}")
        return escaped


def format_xrp_address(address: str) -> str:
    """
    Format XRP address for Telegram display with proper escaping

    Args:
        address: XRP address to format

    Returns:
        Formatted address safe for MarkdownV2 with inline code formatting
    """
    # Keep the address in inline code format
    return f"`{address}`"


def format_amount(amount: float, currency: str = "XRP") -> str:
    """
    Format currency amount with proper escaping

    Args:
        amount: The amount to format
        currency: Currency symbol/code

    Returns:
        Formatted amount safe for MarkdownV2
    """
    formatted = f"{amount:.6f} {currency}"
    return escape_markdown_v2(formatted)


def bold(text: str) -> str:
    """
    Make text bold in MarkdownV2

    Args:
        text: Text to make bold

    Returns:
        Bold formatted text
    """
    escaped = escape_markdown_v2(text)
    return f"*{escaped}*"


def italic(text: str) -> str:
    """
    Make text italic in MarkdownV2

    Args:
        text: Text to make italic

    Returns:
        Italic formatted text
    """
    escaped = escape_markdown_v2(text)
    return f"_{escaped}_"


def link(text: str, url: str) -> str:
    """
    Create a hyperlink in MarkdownV2

    Args:
        text: Link text
        url: URL to link to

    Returns:
        Formatted hyperlink
    """
    escaped_text = escape_markdown_v2(text)
    # URLs should not be escaped
    return f"[{escaped_text}]({url})"


# Update message templates to use these utilities
class SafeMessageTemplates:
    """
    Message templates with automatic MarkdownV2 escaping
    """

    @staticmethod
    def welcome_new_user() -> str:
        """Welcome message for new users"""
        return f"""
🎉 {bold('Welcome to XRP Ledger Bot!')}

I'm here to help you manage XRP on the TestNet\\.

Setting up your wallet\\.\\.\\. ⏳
"""

    @staticmethod
    def wallet_created(address: str, balance: float) -> str:
        """Wallet creation success message"""
        return f"""
✅ {bold('Wallet Created Successfully!')}

📬 {bold('Your XRP Address:')}
{format_xrp_address(address)}

💰 {bold('Initial Balance:')} {format_amount(balance)}

⚠️ {italic('This is TestNet XRP for testing only')}

Use /help to see available commands\\.
"""

    @staticmethod
    def balance_info(address: str, balance: float, usd_value: float, timestamp: str) -> str:
        """Balance information message"""
        escaped_timestamp = escape_markdown_v2(timestamp)
        return f"""
💰 {bold('Your Balance')}

📬 {bold('Address:')} {format_xrp_address(address)}
💵 {bold('Balance:')} {format_amount(balance)}
📈 {bold('USD Value:')} ${escape_markdown_v2(f'{usd_value:.2f}')}

Last updated: {escaped_timestamp}
"""

    @staticmethod
    def transaction_success(amount: float, recipient: str, fee: float, tx_hash: str) -> str:
        """Transaction success message"""
        explorer_url = f"https://testnet.xrpl.org/transactions/{tx_hash}"
        return f"""
✅ {bold('Transaction Successful!')}

{bold('Amount:')} {format_amount(amount)}
{bold('To:')} {format_xrp_address(recipient)}
{bold('Fee:')} {format_amount(fee)}

{bold('Transaction Hash:')}
{format_xrp_address(tx_hash)}

{link('View on explorer', explorer_url)}
"""

    @staticmethod
    def error_message(error: str) -> str:
        """Format error message"""
        escaped_error = escape_markdown_v2(error)
        return f"❌ {bold('Error')}\n\n{escaped_error}"
