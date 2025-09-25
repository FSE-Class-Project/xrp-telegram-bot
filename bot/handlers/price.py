# bot/handlers/price.py
import logging
from typing import Any

import httpx
from telegram import Update
from telegram.constants import ParseMode
from telegram.ext import ContextTypes

from ..keyboards.menus import keyboards
from ..utils.formatting import (
    format_error_message,
    format_price_heatmap,
)

HEATMAP_TIMEFRAMES = {"1D", "7D", "30D", "90D", "1Y"}
TIMEFRAME_LABELS = {
    "1D": "1 Day",
    "7D": "7 Days",
    "30D": "30 Days",
    "90D": "90 Days",
    "1Y": "1 Year",
}
DEFAULT_HEATMAP_TIMEFRAME = "30D"

logger = logging.getLogger(__name__)


async def price_command(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle /price command to display current XRP price information.

    Args:
    ----
        update: Telegram update object
        context: Bot context

    """
    # Handle both message and callback query
    if update.message:
        reply_func = update.message.reply_text
    elif update.callback_query and update.callback_query.message:
        reply_func = update.callback_query.message.edit_text
        await update.callback_query.answer()
    else:
        return

    try:
        # Get API URL from context with fallback
        api_url = context.bot_data.get("api_url", "http://localhost:8000")
        api_key = context.bot_data.get("api_key", "dev-bot-api-key-change-in-production")

        # Fetch user currency
        user_id = (update.effective_user.id if update.effective_user else None) or (
            update.callback_query.from_user.id if update.callback_query else None
        )
        currency = "USD"
        if user_id:
            async with httpx.AsyncClient() as client:
                headers = {"X-API-Key": api_key}
                resp = await client.get(
                    f"{api_url}/api/v1/user/settings/{user_id}",
                    headers=headers,
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    currency = str(resp.json().get("currency_display", "USD")).upper()

        # Fetch price data with market stats
        price_data = await fetch_price_data(api_url, api_key)
        market_data = await fetch_market_stats(api_url, api_key)

        if price_data:
            # Format and send price message with enhanced data
            message = format_enhanced_price_message(price_data, market_data, currency)

            await reply_func(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboards.price_menu(),
            )
        else:
            # Send error message
            await reply_func(
                format_error_message("Unable to fetch current price data. Please try again later."),
                parse_mode=ParseMode.HTML,
            )

    except Exception as e:
        logger.error(f"Error in price_command: {e}", exc_info=True)
        await reply_func(
            format_error_message(f"An unexpected error occurred: {str(e)}"),
            parse_mode=ParseMode.HTML,
        )


async def fetch_price_data(api_url: str, api_key: str) -> dict[str, Any] | None:
    """Fetch price data from the API.

    Args:
    ----
        api_url: Base URL of the API
        api_key: API key for authentication

    Returns:
    -------
        Price data dictionary or None if failed

    """
    try:
        async with httpx.AsyncClient() as client:
            headers = {"X-API-Key": api_key}
            response = await client.get(
                f"{api_url}/api/v1/price/current",
                headers=headers,
                timeout=httpx.Timeout(10.0),
            )

            if response.status_code == 200:
                result = response.json()
                return result if isinstance(result, dict) else None
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


async def fetch_market_stats(api_url: str, api_key: str) -> dict[str, Any] | None:
    """Fetch market statistics from API."""
    try:
        async with httpx.AsyncClient() as client:
            headers = {"X-API-Key": api_key}
            response = await client.get(
                f"{api_url}/api/v1/price/market-stats",
                headers=headers,
                timeout=httpx.Timeout(10.0),
            )
            if response.status_code == 200:
                result = response.json()
                return result if isinstance(result, dict) else None
    except Exception as e:
        logger.error(f"Error fetching market stats: {e}")
    return None


async def fetch_price_heatmap(
    api_url: str, api_key: str, timeframe: str, currency: str
) -> dict[str, Any] | None:
    """Fetch price heatmap data from backend."""
    try:
        async with httpx.AsyncClient() as client:
            headers = {"X-API-Key": api_key}
            response = await client.get(
                f"{api_url}/api/v1/price/heatmap",
                headers=headers,
                params={"timeframe": timeframe.upper(), "currency": currency.upper()},
                timeout=httpx.Timeout(10.0),
            )
            if response.status_code == 200:
                result = response.json()
                return result if isinstance(result, dict) else None
            logger.error(
                "Heatmap API returned status %s for timeframe %s",
                response.status_code,
                timeframe,
            )
    except Exception as e:  # noqa: BLE001
        logger.error(f"Error fetching heatmap data: {e}")
    return None


def format_enhanced_price_message(
    price_data: dict[str, Any],
    market_data: dict[str, Any] | None = None,
    currency: str = "USD",
) -> str:
    """Format enhanced price data into an HTML Telegram message.

    Args:
    ----
        price_data: Price data dictionary
        market_data: Optional market statistics
        currency: Target currency for formatting

    Returns:
    -------
        Formatted HTML message string

    """
    # Extract values with defaults
    price_usd = float(price_data.get("price_usd", 0))
    price_btc = float(price_data.get("price_btc", 0))
    price_map = {
        "USD": price_data.get("price_usd"),
        "EUR": price_data.get("price_eur"),
        "GBP": price_data.get("price_gbp"),
        "ZAR": price_data.get("price_zar"),
        "JPY": price_data.get("price_jpy"),
        "ETH": price_data.get("price_eth"),
        "BTC": price_data.get("price_btc"),
    }
    sel_price = float(price_map.get(currency.upper(), price_usd) or price_usd)
    symbols = {"USD": "$", "EUR": "€", "GBP": "£", "ZAR": "R", "JPY": "¥"}
    if currency.upper() in ("BTC", "ETH"):
        sym = "₿" if currency.upper() == "BTC" else "Ξ"
    else:
        sym = symbols.get(currency.upper(), "$")
    change_24h = float(price_data.get("change_24h_percent", price_data.get("change_24h", 0)))
    market_cap = float(price_data.get("market_cap_usd", price_data.get("market_cap", 0)))
    volume_24h = float(price_data.get("volume_24h_usd", price_data.get("volume_24h", 0)))

    # Choose emoji based on price change
    change_emoji = "📈" if change_24h >= 0 else "📉"

    # Build message
    message = f"""
📊 <b>XRP Market Data</b>

💵 <b>Price:</b> {sym}{sel_price:.4f} ({currency})
₿ <b>BTC:</b> {price_btc:.8f} BTC
{change_emoji} <b>24h:</b> {change_24h:+.2f}%

💹 <b>Market Cap:</b> ${market_cap:,.0f}
📦 <b>24h Volume:</b> ${volume_24h:,.0f}
"""

    # Add market stats if available
    if market_data:
        rank = market_data.get("market_cap_rank", "N/A")
        high_24h = market_data.get("high_24h_usd", 0)
        low_24h = market_data.get("low_24h_usd", 0)
        circulating = market_data.get("circulating_supply", 0)

        if rank != "N/A":
            message += f"""
🏆 <b>Rank:</b> #{rank}
📈 <b>24h High:</b> ${high_24h:.4f}
📉 <b>24h Low:</b> ${low_24h:.4f}
🔄 <b>Circulating:</b> {circulating:,.0f} XRP
"""

    # Add cache indicator
    if price_data.get("from_cache"):
        message += "\n📡 <i>Cached data</i>"

    return message


async def market_stats_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Render the XRP price heatmap with timeframe toggles."""
    query = update.callback_query
    if not query:
        return

    data = query.data or ""
    timeframe = DEFAULT_HEATMAP_TIMEFRAME
    if data.startswith("market_stats:"):
        candidate = data.split(":", 1)[1].upper()
        if candidate in HEATMAP_TIMEFRAMES:
            timeframe = candidate
    elif data == "market_stats":
        timeframe = DEFAULT_HEATMAP_TIMEFRAME

    await query.answer(f"Loading {timeframe} heatmap…")

    try:
        api_url = context.bot_data.get("api_url", "http://localhost:8000")
        api_key = context.bot_data.get("api_key", "dev-bot-api-key-change-in-production")

        # Resolve user currency preference
        currency = "USD"
        user_id = query.from_user.id if query.from_user else None
        if user_id:
            async with httpx.AsyncClient() as client:
                headers = {"X-API-Key": api_key}
                resp = await client.get(
                    f"{api_url}/api/v1/user/settings/{user_id}",
                    headers=headers,
                    timeout=10.0,
                )
                if resp.status_code == 200:
                    currency = str(resp.json().get("currency_display", "USD")).upper()

        heatmap_data = await fetch_price_heatmap(api_url, api_key, timeframe, currency)

        fallback_payload = {
            "timeframe": timeframe,
            "label": TIMEFRAME_LABELS.get(timeframe, timeframe),
            "segments": [],
            "resolution": "daily",
        }

        message = format_price_heatmap(heatmap_data or fallback_payload, currency)

        keyboard = keyboards.heatmap_menu(timeframe)

        if query.message:
            await query.message.edit_text(
                message,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )

    except Exception as e:  # noqa: BLE001
        logger.error(f"Error in market_stats_callback: {e}", exc_info=True)
        await query.answer("Unable to load heatmap", show_alert=True)


async def price_refresh_callback(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    """Handle price refresh callback from inline keyboard.

    Args:
    ----
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
        api_url = context.bot_data.get("api_url", "http://localhost:8000")
        api_key = context.bot_data.get("api_key", "dev-bot-api-key-change-in-production")

        # Fetch updated price data
        price_data = await fetch_price_data(api_url, api_key)
        market_data = await fetch_market_stats(api_url, api_key)
        # Get user currency
        currency = "USD"
        user_id = query.from_user.id
        async with httpx.AsyncClient() as client:
            headers = {"X-API-Key": api_key}
            resp = await client.get(
                f"{api_url}/api/v1/user/settings/{user_id}",
                headers=headers,
                timeout=10.0,
            )
            if resp.status_code == 200:
                currency = str(resp.json().get("currency_display", "USD")).upper()

        if price_data and query.message:
            # Update the existing message
            message = format_enhanced_price_message(price_data, market_data, currency)

            await query.message.edit_text(
                text=message,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboards.price_menu(),
            )
        else:
            await query.answer("Failed to refresh price", show_alert=True)

    except Exception as e:
        logger.error(f"Error in price_refresh_callback: {e}")
        await query.answer("An error occurred", show_alert=True)
