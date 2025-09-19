"""XRP price service with caching."""

import logging
from datetime import datetime, timezone
from typing import Any

import httpx

from ..config import settings
from .cache_service import get_cache_service

logger = logging.getLogger(__name__)


class PriceService:
    """Service for fetching and caching XRP price data."""

    def __init__(self):
        """Initialize price service with cache."""
        self.cache = get_cache_service()
        self.api_url = settings.PRICE_API_URL
        self.api_key = settings.PRICE_API_KEY

    async def get_xrp_price(self, force_refresh: bool = False) -> dict[str, Any]:
        """Get XRP price data with caching.

        Args:
        ----
            force_refresh: Force API call even if cached data exists

        Returns:
        -------
            Price data dictionary

        """
        # Check cache first unless forced refresh
        if not force_refresh:
            cached_price = self.cache.get_xrp_price()
            if cached_price:
                cached_price["from_cache"] = True
                return cached_price

        # Fetch from API
        try:
            price_data = await self._fetch_price_from_api()

            # Cache the result
            if price_data:
                self.cache.set_xrp_price(price_data)
                price_data["from_cache"] = False

            return price_data

        except Exception as e:
            logger.error(f"Error fetching XRP price: {e}")

            # Return cached data if available (even if expired)
            cached_price = self.cache.get_xrp_price()
            if cached_price:
                cached_price["from_cache"] = True
                cached_price["stale"] = True
                return cached_price

            # Return error response
            return {
                "error": str(e),
                "price_usd": 0,
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def _fetch_price_from_api(self) -> dict[str, Any]:
        """Fetch XRP price from external API."""
        async with httpx.AsyncClient() as client:
            # CoinGecko API endpoint
            url = f"{self.api_url}/simple/price"
            params = {
                "ids": "ripple",
                "vs_currencies": "usd,btc",
                "include_market_cap": "true",
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
                "include_last_updated_at": "true",
            }

            headers = {}
            if self.api_key:
                headers["x-cg-demo-api-key"] = self.api_key

            response = await client.get(url, params=params, headers=headers, timeout=10.0)
            response.raise_for_status()

            data = response.json()

            # Parse response
            ripple_data = data.get("ripple", {})

            return {
                "price_usd": ripple_data.get("usd", 0),
                "price_btc": ripple_data.get("btc", 0),
                "market_cap_usd": ripple_data.get("usd_market_cap", 0),
                "volume_24h_usd": ripple_data.get("usd_24h_vol", 0),
                "change_24h_percent": ripple_data.get("usd_24h_change", 0),
                "last_updated": ripple_data.get("last_updated_at", 0),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "coingecko",
            }

    async def get_price_history(self, days: int = 7, currency: str = "usd") -> dict[str, Any]:
        """Get XRP price history.

        Args:
        ----
            days: Number of days of history
            currency: Currency to get prices in

        Returns:
        -------
            Price history data

        """
        # Check cache for this specific timeframe
        cache_key = f"price:xrp:history:{days}d_{currency}"
        cached_history = self.cache.cache.get_json(cache_key)

        if cached_history:
            cached_history["from_cache"] = True
            return cached_history

        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.api_url}/coins/ripple/market_chart"
                params = {
                    "vs_currency": currency,
                    "days": days,
                    "interval": "daily" if days > 1 else "hourly",
                }

                headers = {}
                if self.api_key:
                    headers["x-cg-demo-api-key"] = self.api_key

                response = await client.get(url, params=params, headers=headers, timeout=10.0)
                response.raise_for_status()

                data = response.json()

                # Parse and format data
                history = {
                    "prices": data.get("prices", []),
                    "market_caps": data.get("market_caps", []),
                    "volumes": data.get("total_volumes", []),
                    "days": days,
                    "currency": currency,
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "from_cache": False,
                }

                # Cache for 1 hour
                self.cache.cache.set_json(cache_key, history, ttl=3600)

                return history

        except Exception as e:
            logger.error(f"Error fetching price history: {e}")
            return {
                "error": str(e),
                "prices": [],
                "days": days,
                "currency": currency,
            }

    def calculate_price_change(
        self, current_price: float, previous_price: float
    ) -> dict[str, float]:
        """Calculate price change metrics."""
        if previous_price == 0:
            return {"change_amount": 0, "change_percent": 0}

        change_amount = current_price - previous_price
        change_percent = (change_amount / previous_price) * 100

        return {
            "change_amount": round(change_amount, 6),
            "change_percent": round(change_percent, 2),
        }

    async def get_market_stats(self) -> dict[str, Any]:
        """Get comprehensive XRP market statistics."""
        # Try cache first
        cached_stats = self.cache.cache.get_json("market:xrp:stats")
        if cached_stats:
            cached_stats["from_cache"] = True
            return cached_stats

        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.api_url}/coins/ripple"
                params = {
                    "localization": "false",
                    "tickers": "false",
                    "community_data": "false",
                    "developer_data": "false",
                }

                headers = {}
                if self.api_key:
                    headers["x-cg-demo-api-key"] = self.api_key

                response = await client.get(url, params=params, headers=headers, timeout=10.0)
                response.raise_for_status()

                data = response.json()
                market_data = data.get("market_data", {})

                stats = {
                    "current_price_usd": market_data.get("current_price", {}).get("usd", 0),
                    "market_cap_usd": market_data.get("market_cap", {}).get("usd", 0),
                    "market_cap_rank": market_data.get("market_cap_rank", 0),
                    "total_volume_usd": market_data.get("total_volume", {}).get("usd", 0),
                    "high_24h_usd": market_data.get("high_24h", {}).get("usd", 0),
                    "low_24h_usd": market_data.get("low_24h", {}).get("usd", 0),
                    "price_change_24h": market_data.get("price_change_24h", 0),
                    "price_change_percentage_24h": market_data.get(
                        "price_change_percentage_24h", 0
                    ),
                    "price_change_percentage_7d": market_data.get("price_change_percentage_7d", 0),
                    "price_change_percentage_30d": market_data.get(
                        "price_change_percentage_30d", 0
                    ),
                    "circulating_supply": market_data.get("circulating_supply", 0),
                    "total_supply": market_data.get("total_supply", 0),
                    "max_supply": market_data.get("max_supply", 0),
                    "ath": market_data.get("ath", {}).get("usd", 0),
                    "ath_date": market_data.get("ath_date", {}).get("usd", ""),
                    "atl": market_data.get("atl", {}).get("usd", 0),
                    "atl_date": market_data.get("atl_date", {}).get("usd", ""),
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "from_cache": False,
                }

                # Cache for 5 minutes
                self.cache.cache.set_json("market:xrp:stats", stats, ttl=300)

                return stats

        except Exception as e:
            logger.error(f"Error fetching market stats: {e}")
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


# Create singleton instance
price_service = PriceService()
