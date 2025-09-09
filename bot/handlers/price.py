# bot/handlers/price.py
from typing import Optional, Dict, Any
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
import httpx
from datetime import datetime
import logging

from .base import ensure_message, safe_reply_text, escape_markdown_v2, MessageBuilder

logger = logging.getLogger(__name__)

@ensure_message
async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /price command to display current XRP price information.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    # Type assertion - decorator ensures message exists
    assert update.message is not None
    
    try:
        # Get API URL from context with fallback
        api_url = context.bot_data.get('api_url', 'http://localhost:8000')
        
        # Fetch price data
        price_data = await fetch_price_data(api_url)
        
        if price_data:
            # Format and send price message
            message = format_price_message(price_data)
            await safe_reply_text(
                update.message,
                message,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        else:
            # Send error message
            await safe_reply_text(
                update.message,
                MessageBuilder.error_message(
                    "Price service unavailable",
                    "Please try again later"
                ),
                parse_mode=ParseMode.MARKDOWN_V2
            )
                
    except Exception as e:
        logger.error(f"Error in price_command: {e}", exc_info=True)
        await safe_reply_text(
            update.message,
            MessageBuilder.error_message(
                "An unexpected error occurred",
                str(e)
            ),
            parse_mode=ParseMode.MARKDOWN_V2
        )

async def fetch_price_data(api_url: str) -> Optional[Dict[str, Any]]:
    """
    Fetch price data from the API.
    
    Args:
        api_url: Base URL of the API
        
    Returns:
        Price data dictionary or None if failed
    """
    try:
        async with httpx.AsyncClient() as client:
            response = await client.get(
                f"{api_url}/api/v1/price/current",
                timeout=httpx.Timeout(10.0)
            )
            
            if response.status_code == 200:
                return response.json()
            else:
                logger.error(f"Price API returned status {response.status_code}")
                return None
                
    except httpx.TimeoutException:
        logger.error("Price API request timed out")
        return None
    except httpx.RequestError as e:
        logger.error(f"Price API request failed: {e}")
        return None
    except Exception as e:
        logger.error(f"Unexpected error fetching price: {e}")
        return None

def format_price_message(data: Dict[str, Any]) -> str:
    """
    Format price data into a Telegram message.
    
    Args:
        data: Price data dictionary
        
    Returns:
        Formatted message string
    """
    # Extract values with defaults
    price_usd = data.get('price_usd', 0)
    change_24h = data.get('change_24h', 0)
    market_cap = data.get('market_cap', 0)
    volume_24h = data.get('volume_24h', 0)
    
    # Choose emoji based on price change
    change_emoji = "📈" if change_24h >= 0 else "📉"
    
    # Format timestamp
    timestamp = datetime.now().strftime('%Y\\-m\\-d %H:%M:%S UTC')
    
    # Build message with escaped special characters
    message_parts = [
        "📊 *XRP Price Information*",
        "",
        f"💵 *Current Price:* \\${price_usd:.4f}",
        f"{change_emoji} *24h Change:* {change_24h:+.2f}%",
        f"💹 *Market Cap:* \\${market_cap:,.0f}",
        f"📊 *24h Volume:* \\${volume_24h:,.0f}",
        "",
        f"_Last updated: {timestamp}_"
    ]
    
    # Join with escaped newlines
    return '\n'.join(message_parts)

# Optional: Add a callback query handler for inline keyboard buttons
async def price_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle price refresh callback from inline keyboard.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    query = update.callback_query
    if not query:
        return
    
    # Acknowledge the callback
    await query.answer("Refreshing price...")
    
    try:
        # Get API URL from context
        api_url = context.bot_data.get('api_url', 'http://localhost:8000')
        
        # Fetch updated price data
        price_data = await fetch_price_data(api_url)
        
        if price_data and query.message:
            # Update the existing message
            message = format_price_message(price_data)
            await query.message.edit_text(
                text=message,
                parse_mode=ParseMode.MARKDOWN_V2
            )
        else:
            await query.answer("Failed to refresh price", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in price_refresh_callback: {e}")
        await query.answer("An error occurred", show_alert=True)