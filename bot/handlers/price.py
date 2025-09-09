# bot/handlers/price.py
from typing import Optional, Dict, Any
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.constants import ParseMode
from telegram.ext import ContextTypes
import httpx
from datetime import datetime
import logging

from ..utils.formatting import (
    escape_html,
    format_error_message,
    format_success_message,
)
from ..keyboards.menus import keyboards

logger = logging.getLogger(__name__)

async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """
    Handle /price command to display current XRP price information.
    
    Args:
        update: Telegram update object
        context: Bot context
    """
    # Handle both message and callback query
    if update.message:
        reply_func = update.message.reply_text
    elif update.callback_query:
        reply_func = update.callback_query.message.edit_text
        await update.callback_query.answer()
    else:
        return
    
    try:
        # Get API URL from context with fallback
        api_url = context.bot_data.get('api_url', 'http://localhost:8000')
        api_key = context.bot_data.get('api_key', 'dev-bot-api-key-change-in-production')
        
        # Fetch price data with market stats
        price_data = await fetch_price_data(api_url, api_key)
        market_data = await fetch_market_stats(api_url, api_key)
        
        if price_data:
            # Format and send price message with enhanced data
            message = format_enhanced_price_message(price_data, market_data)
            
            # Add inline keyboard for actions
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data="refresh_price"),
                    InlineKeyboardButton("📈 Market Stats", callback_data="market_stats")
                ],
                [
                    InlineKeyboardButton("💰 Balance", callback_data="balance"),
                    InlineKeyboardButton("📤 Send XRP", callback_data="send")
                ],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ])
            
            await reply_func(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        else:
            # Send error message
            await reply_func(
                format_error_message(
                    "Price Service Unavailable",
                    "Unable to fetch current price data. Please try again later."
                ),
                parse_mode=ParseMode.HTML
            )
                
    except Exception as e:
        logger.error(f"Error in price_command: {e}", exc_info=True)
        await reply_func(
            format_error_message(
                "An unexpected error occurred",
                str(e)
            ),
            parse_mode=ParseMode.HTML
        )

async def fetch_price_data(api_url: str, api_key: str) -> Optional[Dict[str, Any]]:
    """
    Fetch price data from the API.
    
    Args:
        api_url: Base URL of the API
        api_key: API key for authentication
        
    Returns:
        Price data dictionary or None if failed
    """
    try:
        async with httpx.AsyncClient() as client:
            headers = {"X-API-Key": api_key}
            response = await client.get(
                f"{api_url}/api/v1/price/current",
                headers=headers,
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

async def fetch_market_stats(api_url: str, api_key: str) -> Optional[Dict[str, Any]]:
    """Fetch market statistics from API."""
    try:
        async with httpx.AsyncClient() as client:
            headers = {"X-API-Key": api_key}
            response = await client.get(
                f"{api_url}/api/v1/price/market-stats",
                headers=headers,
                timeout=httpx.Timeout(10.0)
            )
            if response.status_code == 200:
                return response.json()
    except Exception as e:
        logger.error(f"Error fetching market stats: {e}")
    return None

def format_enhanced_price_message(price_data: Dict[str, Any], market_data: Optional[Dict[str, Any]] = None) -> str:
    """
    Format enhanced price data into an HTML Telegram message.
    
    Args:
        price_data: Price data dictionary
        market_data: Optional market statistics
        
    Returns:
        Formatted HTML message string
    """
    # Extract values with defaults
    price_usd = price_data.get('price_usd', 0)
    price_btc = price_data.get('price_btc', 0)
    change_24h = price_data.get('change_24h_percent', price_data.get('change_24h', 0))
    market_cap = price_data.get('market_cap_usd', price_data.get('market_cap', 0))
    volume_24h = price_data.get('volume_24h_usd', price_data.get('volume_24h', 0))
    
    # Choose emoji based on price change
    change_emoji = "📈" if change_24h >= 0 else "📉"
    
    # Build message
    message = f"""
📊 <b>XRP Market Data</b>

💵 <b>Price:</b> ${price_usd:.4f}
₿ <b>BTC:</b> {price_btc:.8f} BTC
{change_emoji} <b>24h:</b> {change_24h:+.2f}%

💹 <b>Market Cap:</b> ${market_cap:,.0f}
📦 <b>24h Volume:</b> ${volume_24h:,.0f}
"""
    
    # Add market stats if available
    if market_data:
        rank = market_data.get('market_cap_rank', 'N/A')
        high_24h = market_data.get('high_24h_usd', 0)
        low_24h = market_data.get('low_24h_usd', 0)
        circulating = market_data.get('circulating_supply', 0)
        
        if rank != 'N/A':
            message += f"""
🏆 <b>Rank:</b> #{rank}
📈 <b>24h High:</b> ${high_24h:.4f}
📉 <b>24h Low:</b> ${low_24h:.4f}
🔄 <b>Circulating:</b> {circulating:,.0f} XRP
"""
    
    # Add cache indicator
    if price_data.get('from_cache'):
        message += "\n📡 <i>Cached data</i>"
    
    return message

async def market_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle market statistics callback."""
    query = update.callback_query
    if not query:
        return
    
    await query.answer("Loading market statistics...")
    
    try:
        api_url = context.bot_data.get('api_url', 'http://localhost:8000')
        api_key = context.bot_data.get('api_key', 'dev-bot-api-key-change-in-production')
        
        # Fetch comprehensive market data
        async with httpx.AsyncClient() as client:
            headers = {"X-API-Key": api_key}
            response = await client.get(
                f"{api_url}/api/v1/price/market-stats",
                headers=headers,
                timeout=10.0
            )
            
            if response.status_code == 200:
                data = response.json()
                
                message = f"""
📈 <b>XRP Market Statistics</b>

<b>Rankings:</b>
🏆 Market Cap Rank: #{data.get('market_cap_rank', 'N/A')}
💰 Market Cap: ${data.get('market_cap_usd', 0):,.0f}

<b>Price Movement:</b>
📈 24h Change: {data.get('price_change_percentage_24h', 0):+.2f}%
📅 7d Change: {data.get('price_change_percentage_7d', 0):+.2f}%
📆 30d Change: {data.get('price_change_percentage_30d', 0):+.2f}%

<b>All-Time Records:</b>
🚀 ATH: ${data.get('ath', 0):.4f}
📉 ATL: ${data.get('atl', 0):.6f}

<b>Supply:</b>
🔄 Circulating: {data.get('circulating_supply', 0):,.0f}
🎯 Total: {data.get('total_supply', 0):,.0f}
🔒 Max: {data.get('max_supply', 0):,.0f}
"""
                
                keyboard = InlineKeyboardMarkup([[
                    InlineKeyboardButton("🔙 Back", callback_data="price"),
                    InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")
                ]])
                
                await query.message.edit_text(
                    message,
                    parse_mode=ParseMode.HTML,
                    reply_markup=keyboard
                )
            else:
                await query.answer("Failed to load market data", show_alert=True)
                
    except Exception as e:
        logger.error(f"Error in market_stats_callback: {e}")
        await query.answer("An error occurred", show_alert=True)

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
        api_key = context.bot_data.get('api_key', 'dev-bot-api-key-change-in-production')
        
        # Fetch updated price data
        price_data = await fetch_price_data(api_url, api_key)
        market_data = await fetch_market_stats(api_url, api_key)
        
        if price_data and query.message:
            # Update the existing message
            message = format_enhanced_price_message(price_data, market_data)
            
            # Keep the same keyboard
            keyboard = InlineKeyboardMarkup([
                [
                    InlineKeyboardButton("🔄 Refresh", callback_data="refresh_price"),
                    InlineKeyboardButton("📈 Market Stats", callback_data="market_stats")
                ],
                [
                    InlineKeyboardButton("💰 Balance", callback_data="balance"),
                    InlineKeyboardButton("📤 Send XRP", callback_data="send")
                ],
                [InlineKeyboardButton("🏠 Main Menu", callback_data="main_menu")]
            ])
            
            await query.message.edit_text(
                text=message,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard
            )
        else:
            await query.answer("Failed to refresh price", show_alert=True)
            
    except Exception as e:
        logger.error(f"Error in price_refresh_callback: {e}")
        await query.answer("An error occurred", show_alert=True)