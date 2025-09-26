"""XRP price service."""

from __future__ import annotations

import asyncio
import logging
from datetime import datetime, timedelta, timezone
from typing import Any

import httpx

from ..config import settings
from .cache_service import get_cache_service

logger = logging.getLogger(__name__)


FLAT_THRESHOLD = 0.5


TIMEFRAME_CONFIG: dict[str, dict[str, Any]] = {
    "1D": {
        "days": 1,
        "max_segments": 24,
        "label": "1 Day",
        "resolution": "hourly",
        "interval": "hourly",
    },
    "7D": {
        "days": 7,
        "max_segments": 7,
        "label": "7 Days",
        "resolution": "daily",
        "interval": "daily",
    },
    "30D": {
        "days": 30,
        "max_segments": 30,
        "label": "30 Days",
        "resolution": "daily",
        "interval": "daily",
    },
    "90D": {
        "days": 90,
        "max_segments": 30,
        "label": "90 Days",
        "resolution": "3-day",
        "interval": "daily",
    },
    "1Y": {
        "days": 365,
        "max_segments": 52,
        "label": "1 Year",
        "resolution": "weekly",
        "interval": "daily",
    },
}


# --- Rate Limiter ---
class RateLimiter:
    """Simple rate limiter for API calls."""

    def __init__(self, max_calls: int = 25, time_window: int = 60):
        """Initialize rate limiter.

        Args:
        ----
            max_calls: Maximum number of calls allowed in time window
            time_window: Time window in seconds

        """
        self.max_calls = max_calls
        self.time_window = time_window
        self.calls: list[datetime] = []
        self._lock = asyncio.Lock()

    async def acquire(self) -> bool:
        """Check if we can make a call within rate limits.

        Returns
        -------
            True if call is allowed, False if rate limited

        """
        async with self._lock:
            now = datetime.now(timezone.utc)
            cutoff = now - timedelta(seconds=self.time_window)
            self.calls = [c for c in self.calls if c > cutoff]

            if len(self.calls) >= self.max_calls:
                logger.warning(
                    f"Rate limit reached: {len(self.calls)}/{self.max_calls} calls in "
                    f"{self.time_window}s"
                )
                return False

            self.calls.append(now)
            return True

    async def wait_if_needed(self) -> None:
        """Wait until we can make a call within rate limits."""
        while not await self.acquire():
            if self.calls:
                oldest_call = min(self.calls)
                wait_time = (
                    oldest_call + timedelta(seconds=self.time_window) - datetime.now(timezone.utc)
                ).total_seconds()
                if wait_time > 0:
                    logger.info(f"Rate limited. Waiting {wait_time:.1f}s before next API call")
                    await asyncio.sleep(wait_time + 0.1)
                else:
                    await asyncio.sleep(1)
            else:
                await asyncio.sleep(1)


class PriceService:
    """Service for fetching and caching XRP price data with rate limiting."""

    def __init__(self):
        """Initialize price service with cache and rate limiting."""
        self.cache = get_cache_service()
        self.api_url = settings.PRICE_API_URL
        self.api_key = settings.PRICE_API_KEY
        # Initialize rate limiters based on API key availability
        if self.api_key:
            self.rate_limiter = RateLimiter(max_calls=25, time_window=60)
            self.monthly_limiter = RateLimiter(max_calls=9000, time_window=30 * 24 * 3600)
            logger.info("Price service initialized with API key (25 calls/minute limit)")
        else:
            self.rate_limiter = RateLimiter(max_calls=10, time_window=60)
            logger.info("Price service initialized without API key (10 calls/minute limit)")
        # Cache TTL settings
        self.cache_ttl_price = 60
        self.cache_ttl_stats = 300
        self.cache_ttl_history = 3600
        # API call tracking
        self.api_calls_count = 0
        self.api_calls_failed = 0
        self.last_api_call: datetime | None = None

    async def get_xrp_price(self, force_refresh: bool = False) -> dict[str, Any]:
        """Get XRP price data with caching and rate limiting.

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
                if "timestamp" in cached_price:
                    cache_age = (
                        datetime.now(timezone.utc)
                        - datetime.fromisoformat(cached_price["timestamp"])
                    ).total_seconds()
                    cached_price["cache_age_seconds"] = cache_age
                return cached_price

        # Check rate limit before API call
        if not await self.rate_limiter.acquire():
            logger.warning("Rate limited - returning stale cache if available")
            cached_price = self.cache.get_xrp_price()
            if cached_price:
                cached_price["from_cache"] = True
                cached_price["stale"] = True
                cached_price["rate_limited"] = True
                return cached_price
            # Wait for rate limit to clear
            await self.rate_limiter.wait_if_needed()

        # Fetch from API
        try:
            price_data = await self._fetch_price_from_api()

            # Cache the result
            if price_data and "error" not in price_data:
                self.cache.set_xrp_price(price_data)
                price_data["from_cache"] = False
                price_data["api_calls_today"] = self.api_calls_count

            return price_data

        except httpx.HTTPStatusError as e:
            if e.response.status_code == 429:
                logger.error("CoinGecko API rate limit hit (HTTP 429)")
                self._handle_rate_limit_error()
            else:
                logger.error(f"HTTP error fetching XRP price: {e}")
            return self._get_fallback_price_data(str(e))

        except Exception as e:
            logger.error(f"Error fetching XRP price: {e}")
            return self._get_fallback_price_data(str(e))

    async def _fetch_price_from_api(self) -> dict[str, Any]:
        """Fetch XRP price from external API."""
        async with httpx.AsyncClient() as client:
            # CoinGecko API endpoint
            url = f"{self.api_url}/simple/price"
            params = {
                "ids": "ripple",
                "vs_currencies": "usd,eur,gbp,zar,jpy,btc,eth",
                "include_market_cap": "true",
                "include_24hr_vol": "true",
                "include_24hr_change": "true",
                "include_last_updated_at": "true",
            }

            headers = {"Accept": "application/json", "User-Agent": "XRP-Telegram-Bot/1.0"}
            if self.api_key:
                headers["x-cg-demo-api-key"] = self.api_key

            logger.debug(f"Fetching price from CoinGecko API (call #{self.api_calls_count + 1})")
            response = await client.get(
                url, params=params, headers=headers, timeout=10.0, follow_redirects=True
            )

            # Track API calls
            self.api_calls_count += 1
            self.last_api_call = datetime.now(timezone.utc)

            # Log rate limit headers if available
            if "x-ratelimit-remaining" in response.headers:
                logger.info(
                    f"CoinGecko rate limit remaining: "
                    f"{response.headers.get('x-ratelimit-remaining')}"
                )

            response.raise_for_status()
            data = response.json()

            # Parse response
            ripple_data = data.get("ripple", {})

            return {
                "price_usd": ripple_data.get("usd", 0),
                "price_eur": ripple_data.get("eur", 0),
                "price_gbp": ripple_data.get("gbp", 0),
                "price_zar": ripple_data.get("zar", 0),
                "price_jpy": ripple_data.get("jpy", 0),
                "price_btc": ripple_data.get("btc", 0),
                "price_eth": ripple_data.get("eth", 0),
                "market_cap_usd": ripple_data.get("usd_market_cap", 0),
                "volume_24h_usd": ripple_data.get("usd_24h_vol", 0),
                "change_24h_percent": ripple_data.get("usd_24h_change", 0),
                "last_updated": ripple_data.get("last_updated_at", 0),
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "source": "coingecko",
            }

    def _handle_rate_limit_error(self) -> None:
        """Handle rate limit errors by adjusting limiter."""
        self.api_calls_failed += 1
        if self.rate_limiter.max_calls > 5:
            self.rate_limiter.max_calls = max(5, self.rate_limiter.max_calls - 5)
            logger.warning(f"Reduced rate limit to {self.rate_limiter.max_calls} calls/minute")

    def _get_fallback_price_data(self, error_message: str) -> dict[str, Any]:
        """Get fallback price data when API call fails."""
        cached_price = self.cache.get_xrp_price()
        if cached_price:
            cached_price["from_cache"] = True
            cached_price["stale"] = True
            cached_price["error"] = f"Using cached data due to: {error_message}"
            return cached_price

        return {
            "error": error_message,
            "price_usd": 0,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "from_cache": False,
            "api_calls_today": self.api_calls_count,
            "api_calls_failed": self.api_calls_failed,
        }

    async def get_price_history(
        self,
        days: int | str = 7,
        currency: str = "usd",
        interval: str | None = None,
    ) -> dict[str, Any]:
        """Get XRP price history with rate limiting.

        Args:
        ----
            days: Number of days of history
            currency: Currency to get prices in
            interval: Data interval (hourly, daily, etc.)

        Returns:
        -------
            Price history data

        """
        # Check cache for this specific timeframe
        cache_key = f"price:xrp:history:{days}_{currency}"
        cached_history = self.cache.cache.get_json(cache_key)

        if cached_history and isinstance(cached_history, dict):
            cached_history["from_cache"] = True
            return cached_history  # type: ignore[no-any-return]

        # Wait for rate limit if needed
        await self.rate_limiter.wait_if_needed()

        try:
            async with httpx.AsyncClient() as client:
                use_range_endpoint = isinstance(days, int | float) and days > 365

                if use_range_endpoint:
                    url = f"{self.api_url}/coins/ripple/market_chart/range"
                else:
                    url = f"{self.api_url}/coins/ripple/market_chart"
                currency_code = str(currency).lower()
                if use_range_endpoint:
                    now_ts = int(datetime.now(timezone.utc).timestamp())
                    start_ts = now_ts - int(float(days) * 86400)
                    params = {
                        "vs_currency": currency_code,
                        "from": str(start_ts),
                        "to": str(now_ts),
                    }
                else:
                    params = {
                        "vs_currency": currency_code,
                        "days": str(days),
                    }

                # Determine interval preference for CoinGecko
                effective_interval = None
                if not use_range_endpoint:
                    effective_interval = interval or (
                        "hourly" if isinstance(days, int | float) and days <= 1 else "daily"
                    )
                    if days == "max":
                        effective_interval = None

                    if effective_interval:
                        params["interval"] = effective_interval

                headers = {"Accept": "application/json", "User-Agent": "XRP-Telegram-Bot/1.0"}
                if self.api_key:
                    headers["x-cg-demo-api-key"] = self.api_key

                try:
                    response = await client.get(url, params=params, headers=headers, timeout=10.0)
                    response.raise_for_status()
                except httpx.HTTPStatusError as exc:
                    # Some intervals require paid tiers—retry without interval if applicable
                    if (
                        not use_range_endpoint
                        and params.pop("interval", "")
                        and exc.response.status_code in {400, 401, 403}
                    ):
                        retry_resp = await client.get(
                            url, params=params, headers=headers, timeout=10.0
                        )
                        retry_resp.raise_for_status()
                        response = retry_resp
                    else:
                        raise

                # Track API calls
                self.api_calls_count += 1
                self.last_api_call = datetime.now(timezone.utc)

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
                self.cache.cache.set_json(cache_key, history, ttl=self.cache_ttl_history)

                return history

        except Exception as e:
            logger.error(f"Error fetching price history: {e}")
            self.api_calls_failed += 1
            # Return cached data if available
            if cached_history:
                cached_history["from_cache"] = True
                cached_history["stale"] = True
                return dict(cached_history)
            return {
                "error": str(e),
                "prices": [],
                "days": days,
                "currency": currency,
            }

    @staticmethod
    def _determine_emoji(change_percent: float) -> str:
        """Map change percentage to heatmap emoji."""
        if change_percent > FLAT_THRESHOLD:
            return "🟩"
        if change_percent < -FLAT_THRESHOLD:
            return "🟥"
        return "🟨"

    @staticmethod
    def _downsample_indices(total_points: int, max_segments: int) -> list[int]:
        """Return indices to sample price points for heatmap generation."""
        if total_points <= 1:
            return [0]
        if total_points <= max_segments + 1:
            return list(range(total_points))

        step = (total_points - 1) / max_segments
        indices: list[int] = [0]

        for i in range(1, max_segments):
            idx = int(i * step)
            if idx <= indices[-1]:
                idx = indices[-1] + 1
            if idx >= total_points:
                idx = total_points - 1
            indices.append(idx)

        if indices[-1] != total_points - 1:
            indices.append(total_points - 1)

        # Ensure strictly increasing sequence and cap length
        cleaned: list[int] = [indices[0]]
        for idx in indices[1:]:
            next_idx = idx
            if next_idx <= cleaned[-1]:
                next_idx = cleaned[-1] + 1
            if next_idx >= total_points:
                next_idx = total_points - 1
            if next_idx > cleaned[-1]:
                cleaned.append(next_idx)

        if cleaned[-1] != total_points - 1:
            cleaned.append(total_points - 1)

        return cleaned

    async def get_price_heatmap(self, timeframe: str, currency: str = "usd") -> dict[str, Any]:
        """Generate emoji heatmap data for XRP price changes."""
        tf_key = timeframe.upper()
        config = TIMEFRAME_CONFIG.get(tf_key)
        if not config:
            raise ValueError(f"Unsupported timeframe: {timeframe}")

        history = await self.get_price_history(
            days=config["days"],
            currency=currency,
            interval=config.get("interval"),
        )

        raw_prices = history.get("prices", [])
        price_points: list[tuple[int, float]] = []
        for entry in raw_prices:
            if not isinstance(entry, list | tuple) or len(entry) < 2:
                continue
            try:
                price_points.append((int(entry[0]), float(entry[1])))
            except (TypeError, ValueError):
                continue

        price_points.sort(key=lambda item: item[0])

        if len(price_points) < 2:
            return {
                "timeframe": tf_key,
                "label": config["label"],
                "currency": currency.lower(),
                "resolution": config.get("resolution", "daily"),
                "segments": [],
                "segment_count": 0,
                "start_price": price_points[0][1] if price_points else 0.0,
                "end_price": price_points[-1][1] if price_points else 0.0,
                "overall_change_percent": 0.0,
                "range_start": None,
                "range_end": None,
                "from_cache": history.get("from_cache", False),
                "legend": {
                    "up": "> +0.5%",
                    "flat": "±0.5%",
                    "down": "< -0.5%",
                },
                "last_updated": datetime.now(timezone.utc),
            }

        indices = self._downsample_indices(len(price_points), config["max_segments"])
        segments: list[dict[str, Any]] = []

        for start_idx, end_idx in zip(indices, indices[1:], strict=False):
            if start_idx == end_idx:
                continue
            start_ts, start_price = price_points[start_idx]
            end_ts, end_price = price_points[end_idx]
            if start_price == 0:
                change_percent = 0.0
            else:
                change_percent = ((end_price - start_price) / start_price) * 100

            segments.append(
                {
                    "start_timestamp": datetime.fromtimestamp(start_ts / 1000, tz=timezone.utc),
                    "end_timestamp": datetime.fromtimestamp(end_ts / 1000, tz=timezone.utc),
                    "change_percent": round(change_percent, 2),
                    "emoji": self._determine_emoji(change_percent),
                }
            )

        start_idx = indices[0]
        end_idx = indices[-1]
        start_price = price_points[start_idx][1]
        end_price = price_points[end_idx][1]
        overall_change = (
            0.0 if start_price == 0 else ((end_price - start_price) / start_price) * 100
        )

        return {
            "timeframe": tf_key,
            "label": config["label"],
            "currency": currency.lower(),
            "resolution": config.get("resolution", "daily"),
            "segments": segments,
            "segment_count": len(segments),
            "start_price": round(start_price, 6),
            "end_price": round(end_price, 6),
            "overall_change_percent": round(overall_change, 2),
            "range_start": datetime.fromtimestamp(
                price_points[start_idx][0] / 1000, tz=timezone.utc
            ),
            "range_end": datetime.fromtimestamp(price_points[end_idx][0] / 1000, tz=timezone.utc),
            "from_cache": history.get("from_cache", False),
            "legend": {
                "up": "> +0.5%",
                "flat": "±0.5%",
                "down": "< -0.5%",
            },
            "last_updated": datetime.now(timezone.utc),
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
        """Get comprehensive XRP market statistics with rate limiting."""
        # Try cache first
        cached_stats = self.cache.cache.get_json("market:xrp:stats")
        if cached_stats and isinstance(cached_stats, dict):
            cached_stats["from_cache"] = True
            return cached_stats  # type: ignore[no-any-return]

        # Wait for rate limit if needed
        await self.rate_limiter.wait_if_needed()

        try:
            async with httpx.AsyncClient() as client:
                url = f"{self.api_url}/coins/ripple"
                params = {
                    "localization": "false",
                    "tickers": "false",
                    "community_data": "false",
                    "developer_data": "false",
                }

                headers = {"Accept": "application/json", "User-Agent": "XRP-Telegram-Bot/1.0"}
                if self.api_key:
                    headers["x-cg-demo-api-key"] = self.api_key

                response = await client.get(url, params=params, headers=headers, timeout=10.0)
                # Track API calls
                self.api_calls_count += 1
                self.last_api_call = datetime.now(timezone.utc)
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
                self.cache.cache.set_json("market:xrp:stats", stats, ttl=self.cache_ttl_stats)

                return stats

        except Exception as e:
            logger.error(f"Error fetching market stats: {e}")
            self.api_calls_failed += 1
            # Return cached data if available
            if cached_stats:
                cached_stats["from_cache"] = True
                cached_stats["stale"] = True
                return dict(cached_stats)
            return {
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }


# Create singleton instance
price_service = PriceService()
