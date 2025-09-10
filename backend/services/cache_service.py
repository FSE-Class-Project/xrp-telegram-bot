"""Redis caching service for improved performance."""

import json
import logging
import pickle
from contextlib import contextmanager
from typing import Any

import redis
from redis.exceptions import ConnectionError as RedisConnectionError
from redis.exceptions import RedisError

from ..config import settings

logger = logging.getLogger(__name__)


class CacheKeys:
    """Centralized cache key patterns."""

    # User and wallet keys
    USER_BY_ID = "user:id:{user_id}"
    USER_BY_TELEGRAM = "user:telegram:{telegram_id}"
    WALLET_BY_USER = "wallet:user:{user_id}"
    WALLET_BY_ADDRESS = "wallet:address:{address}"

    # Balance and transaction keys
    BALANCE_BY_ADDRESS = "balance:{address}"
    TRANSACTION_BY_HASH = "tx:hash:{tx_hash}"
    TRANSACTION_HISTORY = "tx:history:{user_id}:{page}"

    # Price data keys
    XRP_PRICE = "price:xrp:usd"
    XRP_PRICE_HISTORY = "price:xrp:history:{timeframe}"
    MARKET_DATA = "market:xrp:data"

    # Idempotency keys
    IDEMPOTENCY_RECORD = "idempotency:{key}"

    # Rate limiting keys
    RATE_LIMIT = "ratelimit:{endpoint}:{identifier}"

    # Lock keys for distributed operations
    LOCK_TRANSACTION = "lock:tx:{user_id}"
    LOCK_WALLET_UPDATE = "lock:wallet:{wallet_id}"


class RedisCache:
    """Redis cache implementation with connection pooling and error handling."""

    def __init__(
        self,
        host: str = "localhost",
        port: int = 6379,
        db: int = 0,
        password: str | None = None,
        decode_responses: bool = False,
        max_connections: int = 50,
        socket_timeout: int = 5,
        connection_timeout: int = 5,
        retry_on_timeout: bool = True,
    ):
        """Initialize Redis connection with pooling."""
        self.pool = redis.ConnectionPool(
            host=host,
            port=port,
            db=db,
            password=password,
            decode_responses=decode_responses,
            max_connections=max_connections,
            socket_timeout=socket_timeout,
            socket_connect_timeout=connection_timeout,
            retry_on_timeout=retry_on_timeout,
            health_check_interval=30,
        )
        self.client = redis.Redis(connection_pool=self.pool)
        self._connected = False
        self._test_connection()

    def _test_connection(self) -> bool:
        """Test Redis connection."""
        try:
            self.client.ping()
            self._connected = True
            logger.info("✅ Redis connection established")
            return True
        except (RedisError, RedisConnectionError) as e:
            self._connected = False
            logger.warning(f"⚠️ Redis connection failed: {e}")
            return False

    @property
    def is_connected(self) -> bool:
        """Check if Redis is connected."""
        return self._connected

    def _safe_execute(self, operation, *args, **kwargs) -> Any | None:
        """Safely execute Redis operation with error handling."""
        if not self._connected:
            self._test_connection()
            if not self._connected:
                return None

        try:
            return operation(*args, **kwargs)
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Redis operation failed: {e}")
            self._connected = False
            return None

    # Basic operations
    def get(self, key: str) -> str | bytes | None:
        """Get value from cache."""
        return self._safe_execute(self.client.get, key)

    def set(self, key: str, value: str | bytes, ttl: int | None = None) -> bool:
        """Set value in cache with optional TTL in seconds."""
        result = self._safe_execute(self.client.set, key, value, ex=ttl)
        return bool(result)

    def delete(self, *keys: str) -> int:
        """Delete one or more keys."""
        if not keys:
            return 0
        result = self._safe_execute(self.client.delete, *keys)
        return result or 0

    def exists(self, *keys: str) -> int:
        """Check if keys exist."""
        if not keys:
            return 0
        result = self._safe_execute(self.client.exists, *keys)
        return result or 0

    def expire(self, key: str, ttl: int) -> bool:
        """Set TTL for a key in seconds."""
        result = self._safe_execute(self.client.expire, key, ttl)
        return bool(result)

    def ttl(self, key: str) -> int:
        """Get remaining TTL for a key in seconds."""
        result = self._safe_execute(self.client.ttl, key)
        return result or -2

    # JSON operations
    def get_json(self, key: str) -> Any | None:
        """Get JSON value from cache."""
        value = self.get(key)
        if value:
            try:
                return json.loads(value)
            except json.JSONDecodeError:
                logger.error(f"Failed to decode JSON for key: {key}")
        return None

    def set_json(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set JSON value in cache."""
        try:
            json_value = json.dumps(value)
            return self.set(key, json_value, ttl)
        except (TypeError, json.JSONEncodeError) as e:
            logger.error(f"Failed to encode JSON for key {key}: {e}")
            return False

    # Object operations (using pickle)
    def get_object(self, key: str) -> Any | None:
        """Get pickled object from cache."""
        value = self.get(key)
        if value:
            try:
                return pickle.loads(value)
            except (pickle.PickleError, TypeError) as e:
                logger.error(f"Failed to unpickle object for key {key}: {e}")
        return None

    def set_object(self, key: str, value: Any, ttl: int | None = None) -> bool:
        """Set pickled object in cache."""
        try:
            pickled_value = pickle.dumps(value)
            return self.set(key, pickled_value, ttl)
        except (pickle.PickleError, TypeError) as e:
            logger.error(f"Failed to pickle object for key {key}: {e}")
            return False

    # Hash operations
    def hget(self, key: str, field: str) -> str | bytes | None:
        """Get hash field value."""
        return self._safe_execute(self.client.hget, key, field)

    def hset(self, key: str, field: str, value: str | bytes) -> int:
        """Set hash field value."""
        result = self._safe_execute(self.client.hset, key, field, value)
        return result or 0

    def hgetall(self, key: str) -> dict[str, str]:
        """Get all hash fields and values."""
        result = self._safe_execute(self.client.hgetall, key)
        return result or {}

    def hdel(self, key: str, *fields: str) -> int:
        """Delete hash fields."""
        if not fields:
            return 0
        result = self._safe_execute(self.client.hdel, key, *fields)
        return result or 0

    # List operations
    def lpush(self, key: str, *values: str | bytes) -> int:
        """Push values to the left of a list."""
        if not values:
            return 0
        result = self._safe_execute(self.client.lpush, key, *values)
        return result or 0

    def lrange(self, key: str, start: int, stop: int) -> list[str | bytes]:
        """Get list range."""
        result = self._safe_execute(self.client.lrange, key, start, stop)
        return result or []

    def ltrim(self, key: str, start: int, stop: int) -> bool:
        """Trim list to specified range."""
        result = self._safe_execute(self.client.ltrim, key, start, stop)
        return bool(result)

    # Set operations
    def sadd(self, key: str, *members: str | bytes) -> int:
        """Add members to a set."""
        if not members:
            return 0
        result = self._safe_execute(self.client.sadd, key, *members)
        return result or 0

    def srem(self, key: str, *members: str | bytes) -> int:
        """Remove members from a set."""
        if not members:
            return 0
        result = self._safe_execute(self.client.srem, key, *members)
        return result or 0

    def smembers(self, key: str) -> set:
        """Get all set members."""
        result = self._safe_execute(self.client.smembers, key)
        return result or set()

    def sismember(self, key: str, member: str | bytes) -> bool:
        """Check if member exists in set."""
        result = self._safe_execute(self.client.sismember, key, member)
        return bool(result)

    # Atomic operations
    def incr(self, key: str, amount: int = 1) -> int | None:
        """Increment value atomically."""
        return self._safe_execute(self.client.incr, key, amount)

    def decr(self, key: str, amount: int = 1) -> int | None:
        """Decrement value atomically."""
        return self._safe_execute(self.client.decr, key, amount)

    # Pattern operations
    def keys(self, pattern: str) -> list[str]:
        """Get keys matching pattern (use with caution in production)."""
        result = self._safe_execute(self.client.keys, pattern)
        return result or []

    def scan_iter(self, match: str | None = None, count: int = 100):
        """Scan keys matching pattern (production-safe)."""
        try:
            yield from self.client.scan_iter(match=match, count=count)
        except (RedisError, RedisConnectionError) as e:
            logger.error(f"Scan operation failed: {e}")
            return

    # Distributed locking
    @contextmanager
    def lock(self, key: str, timeout: int = 10, blocking_timeout: int | None = None):
        """Distributed lock context manager."""
        lock = self.client.lock(key, timeout=timeout, blocking_timeout=blocking_timeout)
        acquired = False
        try:
            acquired = lock.acquire()
            if acquired:
                yield lock
            else:
                raise TimeoutError(f"Could not acquire lock for {key}")
        finally:
            if acquired:
                try:
                    lock.release()
                except redis.exceptions.LockError:
                    pass  # Lock already released or expired

    # Batch operations
    def pipeline(self):
        """Create a pipeline for batch operations."""
        return self.client.pipeline()

    # Cache invalidation
    def invalidate_pattern(self, pattern: str) -> int:
        """Invalidate all keys matching pattern."""
        keys = list(self.scan_iter(match=pattern))
        if keys:
            return self.delete(*keys)
        return 0

    def flush_db(self) -> bool:
        """Flush entire database (use with extreme caution)."""
        result = self._safe_execute(self.client.flushdb)
        return bool(result)


class CacheService:
    """High-level caching service with business logic."""

    def __init__(self, redis_url: str | None = None):
        """Initialize cache service."""
        if redis_url:
            # Parse Redis URL
            from urllib.parse import urlparse

            parsed = urlparse(redis_url)
            self.cache = RedisCache(
                host=parsed.hostname or "localhost",
                port=parsed.port or 6379,
                password=parsed.password,
                db=int(parsed.path[1:]) if parsed.path else 0,
            )
        else:
            self.cache = RedisCache()

        self.enabled = self.cache.is_connected

        # Default TTLs
        self.ttl_user = 3600  # 1 hour
        self.ttl_wallet = 3600  # 1 hour
        self.ttl_balance = 60  # 1 minute
        self.ttl_price = 30  # 30 seconds
        self.ttl_transaction = 86400  # 24 hours
        self.ttl_idempotency = 3600  # 1 hour

    # User caching
    def get_user(self, telegram_id: str) -> dict[str, Any] | None:
        """Get cached user data."""
        if not self.enabled:
            return None

        key = CacheKeys.USER_BY_TELEGRAM.format(telegram_id=telegram_id)
        return self.cache.get_json(key)

    def set_user(self, telegram_id: str, user_data: dict[str, Any]) -> bool:
        """Cache user data."""
        if not self.enabled:
            return False

        key = CacheKeys.USER_BY_TELEGRAM.format(telegram_id=telegram_id)
        return self.cache.set_json(key, user_data, self.ttl_user)

    def invalidate_user(self, telegram_id: str) -> bool:
        """Invalidate user cache."""
        if not self.enabled:
            return False

        key = CacheKeys.USER_BY_TELEGRAM.format(telegram_id=telegram_id)
        return bool(self.cache.delete(key))

    # Wallet caching
    def get_wallet(self, user_id: int) -> dict[str, Any] | None:
        """Get cached wallet data."""
        if not self.enabled:
            return None

        key = CacheKeys.WALLET_BY_USER.format(user_id=user_id)
        return self.cache.get_json(key)

    def set_wallet(self, user_id: int, wallet_data: dict[str, Any]) -> bool:
        """Cache wallet data."""
        if not self.enabled:
            return False

        key = CacheKeys.WALLET_BY_USER.format(user_id=user_id)
        return self.cache.set_json(key, wallet_data, self.ttl_wallet)

    # Balance caching
    def get_balance(self, address: str) -> float | None:
        """Get cached balance."""
        if not self.enabled:
            return None

        key = CacheKeys.BALANCE_BY_ADDRESS.format(address=address)
        value = self.cache.get(key)
        if value:
            try:
                return float(value)
            except (ValueError, TypeError):
                pass
        return None

    def set_balance(self, address: str, balance: float) -> bool:
        """Cache balance."""
        if not self.enabled:
            return False

        key = CacheKeys.BALANCE_BY_ADDRESS.format(address=address)
        return self.cache.set(key, str(balance), self.ttl_balance)

    # Price caching
    def get_xrp_price(self) -> dict[str, Any] | None:
        """Get cached XRP price data."""
        if not self.enabled:
            return None

        return self.cache.get_json(CacheKeys.XRP_PRICE)

    def set_xrp_price(self, price_data: dict[str, Any]) -> bool:
        """Cache XRP price data."""
        if not self.enabled:
            return False

        return self.cache.set_json(CacheKeys.XRP_PRICE, price_data, self.ttl_price)

    # Transaction caching
    def get_transaction(self, tx_hash: str) -> dict[str, Any] | None:
        """Get cached transaction."""
        if not self.enabled:
            return None

        key = CacheKeys.TRANSACTION_BY_HASH.format(tx_hash=tx_hash)
        return self.cache.get_json(key)

    def set_transaction(self, tx_hash: str, tx_data: dict[str, Any]) -> bool:
        """Cache transaction."""
        if not self.enabled:
            return False

        key = CacheKeys.TRANSACTION_BY_HASH.format(tx_hash=tx_hash)
        return self.cache.set_json(key, tx_data, self.ttl_transaction)

    # Rate limiting
    def check_rate_limit(
        self, endpoint: str, identifier: str, limit: int, window: int
    ) -> tuple[bool, int]:
        """Check rate limit for endpoint."""
        if not self.enabled:
            return True, 0  # Allow if cache is down

        key = CacheKeys.RATE_LIMIT.format(endpoint=endpoint, identifier=identifier)

        # Use pipeline for atomic operations
        pipe = self.cache.pipeline()
        pipe.incr(key)
        pipe.expire(key, window)
        results = pipe.execute()

        if results:
            count = results[0] or 0
            return count <= limit, count
        return True, 0

    # Distributed locking
    def acquire_transaction_lock(self, user_id: int, timeout: int = 10):
        """Acquire lock for transaction processing."""
        if not self.enabled:
            return None

        key = CacheKeys.LOCK_TRANSACTION.format(user_id=user_id)
        return self.cache.lock(key, timeout=timeout)

    # Cache warming
    def warm_cache(self, data_type: str, data: dict[str, Any]) -> bool:
        """Pre-populate cache with data."""
        if not self.enabled:
            return False

        if data_type == "user":
            return self.set_user(data["telegram_id"], data)
        elif data_type == "wallet":
            return self.set_wallet(data["user_id"], data)
        elif data_type == "price":
            return self.set_xrp_price(data)

        return False

    # Health check
    def health_check(self) -> dict[str, Any]:
        """Check cache health."""
        if not self.cache.is_connected:
            self.cache._test_connection()

        return {
            "connected": self.cache.is_connected,
            "ping": self.cache.client.ping() if self.cache.is_connected else False,
        }


# Create singleton instance
cache_service: CacheService | None = None


def get_cache_service() -> CacheService:
    """Get or create cache service instance."""
    global cache_service

    if cache_service is None:
        redis_url = settings.REDIS_URL
        cache_service = CacheService(redis_url)

        if cache_service.enabled:
            logger.info("✅ Cache service initialized successfully")
        else:
            logger.warning("⚠️ Cache service running in degraded mode (Redis unavailable)")

    return cache_service
