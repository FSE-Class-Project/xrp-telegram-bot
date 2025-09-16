# bot/handlers/base.py
import logging
from collections.abc import Callable
from functools import wraps
from typing import Any, Optional, TypeVar

from telegram import Message, Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Type variable for decorator
F = TypeVar("F", bound=Callable[..., Any])


def ensure_message(func: F) -> F:
    """
    Decorator to ensure update.message exists before processing.
    Prevents None attribute errors in handlers.
    """

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.message:
            logger.warning(f"No message in update for handler {func.__name__}")
            return
        return await func(update, context, *args, **kwargs)

    return wrapper  # type: ignore


def ensure_callback_query(func: F) -> F:
    """
    Decorator to ensure update.callback_query exists.
    """

    @wraps(func)
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE, *args, **kwargs):
        if not update.callback_query:
            logger.warning(f"No callback_query in update for handler {func.__name__}")
            return
        return await func(update, context, *args, **kwargs)

    return wrapper  # type: ignore


async def safe_reply_text(
    message: Optional[Message],
    text: str,
    parse_mode: Optional[str] = ParseMode.MARKDOWN_V2,
    **kwargs,
) -> Optional[Message]:
    """
    Safely reply to a message with proper error handling.

    Args:
        message: The message to reply to
        text: The text to send
        parse_mode: Parse mode for formatting
        **kwargs: Additional arguments for reply_text

    Returns:
        The sent message or None if failed
    """
    if not message:
        logger.error("Cannot reply to None message")
        return None

    try:
        return await message.reply_text(text=text, parse_mode=parse_mode, **kwargs)
    except Exception as e:
        logger.error(f"Error sending message: {e}")
        # Try sending without parse mode if formatting failed
        try:
            return await message.reply_text(text=text, **kwargs)
        except Exception as e2:
            logger.error(f"Failed to send plain text message: {e2}")
            return None


def escape_markdown_v2(text: str) -> str:
    """
    Escape special characters for Telegram's MarkdownV2 format.

    Args:
        text: Text to escape

    Returns:
        Escaped text safe for MarkdownV2
    """
    # Characters that need escaping in MarkdownV2
    escape_chars = [
        "_",
        "*",
        "[",
        "]",
        "(",
        ")",
        "~",
        "`",
        ">",
        "#",
        "+",
        "-",
        "=",
        "|",
        "{",
        "}",
        ".",
        "!",
    ]

    for char in escape_chars:
        text = text.replace(char, f"\\{char}")

    return text


class MessageBuilder:
    """Helper class to build formatted messages safely."""

    @staticmethod
    def error_message(error: str, details: Optional[str] = None) -> str:
        """Build an error message."""
        message = f"❌ *Error*\n\n{escape_markdown_v2(error)}"
        if details:
            message += f"\n\n_{escape_markdown_v2(details)}_"
        return message

    @staticmethod
    def success_message(title: str, content: str) -> str:
        """Build a success message."""
        return f"✅ *{escape_markdown_v2(title)}*\n\n{escape_markdown_v2(content)}"

    @staticmethod
    def info_message(title: str, content: str) -> str:
        """Build an info message."""
        return f"ℹ️ *{escape_markdown_v2(title)}*\n\n{escape_markdown_v2(content)}"
