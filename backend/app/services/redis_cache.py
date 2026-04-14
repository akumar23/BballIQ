"""Redis caching service for NBA API data.

This module provides:
- Redis connection management with automatic reconnection
- Cache get/set operations with configurable TTL
- Key namespacing for organized cache structure
- Graceful fallback when Redis is unavailable
- JSON serialization for complex data types
"""

import json
import logging
from datetime import datetime
from decimal import Decimal
from enum import Enum
from typing import Any, TypeVar

import redis
from redis.exceptions import ConnectionError, RedisError, TimeoutError

from app.core.config import settings


logger = logging.getLogger(__name__)

# Type variable for generic cache operations
T = TypeVar("T")


class CacheKeyPrefix(str, Enum):
    """Cache key prefixes for different data types."""

    NBA_PLAYERS = "nba:players"
    NBA_TRADITIONAL_STATS = "nba:traditional_stats"
    NBA_TOUCH_STATS = "nba:touch_stats"
    NBA_HUSTLE_STATS = "nba:hustle_stats"
    NBA_DEFENSIVE_STATS = "nba:defensive_stats"
    NBA_TRACKING_DATA = "nba:tracking_data"
    NBA_LINEUP_STATS = "nba:lineup_stats"
    NBA_ON_OFF_STATS = "nba:on_off_stats"
    NBA_PLAY_TYPE_STATS = "nba:play_type_stats"
    NBA_ADVANCED_STATS = "nba:advanced_stats"
    NBA_SHOT_LOCATIONS = "nba:shot_locations"
    NBA_LEAGUE_SHOT_AVERAGES = "nba:league_shot_averages"
    NBA_CLUTCH_STATS = "nba:clutch_stats"
    NBA_DEFENSIVE_PLAY_TYPE_STATS = "nba:defensive_play_type_stats"
    NBA_RIM_PROTECTION = "nba:rim_protection"
    NBA_DEFENSE_3PT = "nba:defense_3pt"
    NBA_EFFICIENCY_STATS = "nba:efficiency_stats"
    NBA_TEAM_STATS = "nba:team_stats"
    NBA_PER100_STATS = "nba:per100_stats"
    NBA_CAREER_STATS = "nba:career_stats"
    NBA_CATCH_SHOOT_STATS = "nba:catch_shoot_stats"
    NBA_PULLUP_STATS = "nba:pullup_stats"
    NBA_DRIVE_STATS = "nba:drive_stats"
    NBA_MATCHUP_STATS = "nba:matchup_stats"
    NBA_ALL_IN_ONE_METRICS = "nba:all_in_one_metrics"
    PBP_SEASON_TOTALS = "pbp:season_totals"
    PBP_GAME_POSSESSIONS = "pbp:game_possessions"


class DecimalEncoder(json.JSONEncoder):
    """Custom JSON encoder that handles Decimal types."""

    def default(self, obj: Any) -> Any:
        """Convert Decimal to string for JSON serialization.

        Args:
            obj: Object to encode

        Returns:
            JSON-serializable representation
        """
        if isinstance(obj, Decimal):
            return str(obj)
        return super().default(obj)


class RedisCacheService:
    """Redis caching service with graceful degradation.

    This service provides caching for NBA API data with:
    - Automatic connection management
    - Configurable TTL per data type
    - Graceful fallback when Redis is unavailable
    - Key namespacing for organization

    Attributes:
        _client: Redis client instance
        _connected: Connection status flag
        _last_connection_attempt: Timestamp of last connection attempt
    """

    def __init__(
        self,
        redis_url: str | None = None,
        connection_timeout: int = 5,
        socket_timeout: int = 5,
    ):
        """Initialize the Redis cache service.

        Args:
            redis_url: Redis connection URL (uses config default if None)
            connection_timeout: Connection timeout in seconds
            socket_timeout: Socket timeout in seconds
        """
        self._redis_url = redis_url or settings.redis_url
        self._connection_timeout = connection_timeout
        self._socket_timeout = socket_timeout
        self._client: redis.Redis | None = None
        self._connected: bool = False
        self._last_connection_attempt: datetime | None = None
        self._reconnect_interval: int = 30  # Seconds between reconnection attempts

    def _get_client(self) -> redis.Redis | None:
        """Get or create Redis client with connection checking.

        Returns:
            Redis client if connected, None otherwise
        """
        if not settings.cache_enabled:
            return None

        # Check if we should attempt reconnection
        if not self._connected and self._last_connection_attempt:
            elapsed = (datetime.now() - self._last_connection_attempt).seconds
            if elapsed < self._reconnect_interval:
                return None

        if self._client is None or not self._connected:
            self._last_connection_attempt = datetime.now()
            try:
                self._client = redis.from_url(
                    self._redis_url,
                    socket_connect_timeout=self._connection_timeout,
                    socket_timeout=self._socket_timeout,
                    decode_responses=True,
                )
                # Test connection
                self._client.ping()
                self._connected = True
                logger.info("Connected to Redis at %s", self._redis_url)
            except (ConnectionError, TimeoutError, RedisError) as e:
                logger.warning(
                    "Failed to connect to Redis: %s. Cache operations will be skipped.",
                    e,
                )
                self._connected = False
                self._client = None
                return None

        return self._client

    def _build_key(self, prefix: CacheKeyPrefix | str, *parts: str) -> str:
        """Build a cache key with namespace prefix.

        Args:
            prefix: Key prefix (from CacheKeyPrefix or custom string)
            *parts: Additional key parts to join

        Returns:
            Formatted cache key string
        """
        if isinstance(prefix, CacheKeyPrefix):
            prefix = prefix.value
        all_parts = [prefix] + list(parts)
        return ":".join(all_parts)

    def get(self, key: str) -> Any | None:
        """Get a value from cache.

        Args:
            key: Cache key

        Returns:
            Cached value if found and not expired, None otherwise
        """
        client = self._get_client()
        if client is None:
            logger.debug("Cache miss (Redis unavailable): %s", key)
            return None

        try:
            data = client.get(key)
            if data is None:
                logger.debug("Cache miss: %s", key)
                return None

            logger.debug("Cache hit: %s", key)
            return json.loads(data)

        except (ConnectionError, TimeoutError) as e:
            logger.warning("Redis connection error during get: %s", e)
            self._connected = False
            return None
        except (RedisError, json.JSONDecodeError) as e:
            logger.error("Redis get error for key %s: %s", key, e)
            return None

    def set(
        self,
        key: str,
        value: Any,
        ttl: int | None = None,
    ) -> bool:
        """Set a value in cache with TTL.

        Args:
            key: Cache key
            value: Value to cache (must be JSON-serializable)
            ttl: Time to live in seconds (uses default if None)

        Returns:
            True if successfully cached, False otherwise
        """
        client = self._get_client()
        if client is None:
            logger.debug("Cache set skipped (Redis unavailable): %s", key)
            return False

        ttl = ttl if ttl is not None else settings.cache_ttl_default

        try:
            serialized = json.dumps(value, cls=DecimalEncoder)
            client.setex(key, ttl, serialized)
            logger.debug("Cache set: %s (TTL: %ds)", key, ttl)
            return True

        except (ConnectionError, TimeoutError) as e:
            logger.warning("Redis connection error during set: %s", e)
            self._connected = False
            return False
        except (RedisError, TypeError) as e:
            logger.error("Redis set error for key %s: %s", key, e)
            return False

    def delete(self, key: str) -> bool:
        """Delete a key from cache.

        Args:
            key: Cache key to delete

        Returns:
            True if deleted, False otherwise
        """
        client = self._get_client()
        if client is None:
            return False

        try:
            result = client.delete(key)
            logger.debug("Cache delete: %s (deleted: %s)", key, bool(result))
            return bool(result)

        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.warning("Redis delete error: %s", e)
            self._connected = False
            return False

    def delete_pattern(self, pattern: str) -> int:
        """Delete all keys matching a pattern.

        Args:
            pattern: Glob-style pattern (e.g., "nba:players:*")

        Returns:
            Number of keys deleted
        """
        client = self._get_client()
        if client is None:
            return 0

        try:
            keys = list(client.scan_iter(match=pattern))
            if not keys:
                return 0

            deleted = client.delete(*keys)
            logger.info("Cache pattern delete: %s (%d keys)", pattern, deleted)
            return deleted

        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.warning("Redis pattern delete error: %s", e)
            self._connected = False
            return 0

    def invalidate_season(self, season: str) -> int:
        """Invalidate all cached data for a specific season.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            Number of keys invalidated
        """
        pattern = f"*:{season}"
        return self.delete_pattern(pattern)

    def invalidate_all(self) -> int:
        """Invalidate all NBA-related cache data.

        Returns:
            Number of keys invalidated
        """
        total = 0
        for prefix in CacheKeyPrefix:
            total += self.delete_pattern(f"{prefix.value}:*")
        return total

    def get_ttl(self, key: str) -> int:
        """Get remaining TTL for a key.

        Args:
            key: Cache key

        Returns:
            TTL in seconds, -1 if no TTL, -2 if key doesn't exist
        """
        client = self._get_client()
        if client is None:
            return -2

        try:
            return client.ttl(key)
        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.warning("Redis TTL error: %s", e)
            return -2

    def is_connected(self) -> bool:
        """Check if Redis connection is active.

        Returns:
            True if connected, False otherwise
        """
        client = self._get_client()
        if client is None:
            return False

        try:
            client.ping()
            return True
        except (ConnectionError, TimeoutError, RedisError):
            self._connected = False
            return False

    def get_stats(self) -> dict[str, Any]:
        """Get cache statistics.

        Returns:
            Dictionary with cache statistics
        """
        client = self._get_client()
        if client is None:
            return {
                "connected": False,
                "enabled": settings.cache_enabled,
            }

        try:
            info = client.info("stats")
            keyspace = client.info("keyspace")

            return {
                "connected": True,
                "enabled": settings.cache_enabled,
                "hits": info.get("keyspace_hits", 0),
                "misses": info.get("keyspace_misses", 0),
                "keys": sum(
                    db.get("keys", 0)
                    for db in keyspace.values()
                    if isinstance(db, dict)
                ),
            }
        except (ConnectionError, TimeoutError, RedisError) as e:
            logger.warning("Redis stats error: %s", e)
            return {
                "connected": False,
                "enabled": settings.cache_enabled,
                "error": str(e),
            }


# Singleton instance
redis_cache = RedisCacheService()


def get_cached_or_fetch(
    cache_key: str,
    fetch_func: callable,
    ttl: int | None = None,
    bypass_cache: bool = False,
) -> Any:
    """Helper function to get from cache or fetch and cache.

    This is a convenience function that implements the common pattern:
    1. Check cache for data
    2. If not found (or bypass), fetch from API
    3. Cache the result
    4. Return data

    Args:
        cache_key: Cache key to use
        fetch_func: Function to call if cache miss (should return data)
        ttl: Cache TTL in seconds
        bypass_cache: If True, skip cache lookup and force fetch

    Returns:
        Data from cache or fetch function
    """
    if not bypass_cache:
        cached = redis_cache.get(cache_key)
        if cached is not None:
            return cached

    # Fetch fresh data
    data = fetch_func()

    # Cache the result
    if data is not None:
        redis_cache.set(cache_key, data, ttl=ttl)

    return data
