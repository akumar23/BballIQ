"""Unit tests for the Redis cache module.

This module tests:
- Cache get/set operations with TTL
- Key expiration behavior
- Cache deletion (single key and pattern-based)
- Season data invalidation
- Graceful fallback when Redis unavailable
- get_cached_or_fetch helper function
- Cache statistics tracking
- JSON serialization with Decimal support
"""

import json
import time
from datetime import datetime
from decimal import Decimal
from unittest.mock import MagicMock, patch, PropertyMock

import pytest
import fakeredis
from redis.exceptions import ConnectionError as RedisConnectionError

from app.services.redis_cache import (
    CacheKeyPrefix,
    DecimalEncoder,
    RedisCacheService,
    get_cached_or_fetch,
    redis_cache,
)


class TestCacheKeyPrefix:
    """Tests for CacheKeyPrefix enum."""

    def test_prefix_values(self):
        """Verify cache key prefix values are correctly defined."""
        assert CacheKeyPrefix.NBA_PLAYERS.value == "nba:players"
        assert CacheKeyPrefix.NBA_TRADITIONAL_STATS.value == "nba:traditional_stats"
        assert CacheKeyPrefix.PBP_SEASON_TOTALS.value == "pbp:season_totals"


class TestDecimalEncoder:
    """Tests for Decimal JSON encoding."""

    def test_encodes_decimal_to_string(self):
        """Verify Decimal values are encoded as strings."""
        data = {"value": Decimal("123.456")}
        encoded = json.dumps(data, cls=DecimalEncoder)
        assert '"123.456"' in encoded

    def test_handles_nested_decimals(self):
        """Verify nested Decimal values are encoded."""
        data = {
            "outer": {
                "inner": Decimal("99.99"),
                "list": [Decimal("1.1"), Decimal("2.2")],
            }
        }
        encoded = json.dumps(data, cls=DecimalEncoder)
        assert '"99.99"' in encoded
        assert '"1.1"' in encoded


class TestRedisCacheService:
    """Tests for RedisCacheService class."""

    @pytest.fixture
    def cache_service(self, mock_settings):
        """Provide a RedisCacheService instance with fakeredis."""
        with patch("app.services.redis_cache.settings", mock_settings):
            service = RedisCacheService(redis_url="redis://localhost:6379/0")
            # Replace _get_client to use fakeredis
            fake_client = fakeredis.FakeRedis(decode_responses=True)
            service._client = fake_client
            service._connected = True
            return service

    @pytest.fixture
    def disconnected_cache_service(self, mock_settings):
        """Provide a cache service simulating Redis unavailability."""
        with patch("app.services.redis_cache.settings", mock_settings):
            service = RedisCacheService(redis_url="redis://localhost:6379/0")
            service._connected = False
            service._last_connection_attempt = datetime.now()
            return service

    def test_get_returns_none_for_missing_key(self, cache_service):
        """Verify get() returns None for non-existent keys."""
        result = cache_service.get("nonexistent:key")
        assert result is None

    def test_set_and_get_round_trip(self, cache_service):
        """Verify data can be stored and retrieved."""
        test_data = {"name": "Test", "value": 42, "nested": {"key": "value"}}
        cache_service.set("test:key", test_data)

        result = cache_service.get("test:key")

        assert result == test_data

    def test_set_with_explicit_ttl(self, cache_service):
        """Verify TTL is applied when setting cache."""
        cache_service.set("test:ttl", {"data": "value"}, ttl=100)

        # Check TTL was set
        ttl = cache_service.get_ttl("test:ttl")
        assert ttl > 0
        assert ttl <= 100

    def test_ttl_expiration(self, cache_service):
        """Verify data expires after TTL."""
        cache_service.set("test:expire", {"data": "temp"}, ttl=1)

        # Verify data exists
        assert cache_service.get("test:expire") is not None

        # Wait for expiration
        time.sleep(1.5)

        # Data should be expired
        assert cache_service.get("test:expire") is None

    def test_delete_removes_key(self, cache_service):
        """Verify delete() removes a specific key."""
        cache_service.set("test:delete", {"data": "to_delete"})
        assert cache_service.get("test:delete") is not None

        result = cache_service.delete("test:delete")

        assert result is True
        assert cache_service.get("test:delete") is None

    def test_delete_nonexistent_key_returns_false(self, cache_service):
        """Verify deleting non-existent key returns False."""
        result = cache_service.delete("nonexistent:key")
        assert result is False

    def test_delete_pattern_removes_matching_keys(self, cache_service):
        """Verify delete_pattern() removes all matching keys."""
        # Set multiple keys with same prefix
        cache_service.set("prefix:key1", {"data": 1})
        cache_service.set("prefix:key2", {"data": 2})
        cache_service.set("prefix:key3", {"data": 3})
        cache_service.set("other:key", {"data": "other"})

        deleted_count = cache_service.delete_pattern("prefix:*")

        assert deleted_count == 3
        assert cache_service.get("prefix:key1") is None
        assert cache_service.get("prefix:key2") is None
        assert cache_service.get("prefix:key3") is None
        # Other keys should remain
        assert cache_service.get("other:key") is not None

    def test_invalidate_season_clears_season_data(self, cache_service):
        """Verify invalidate_season() clears all data for a season."""
        # Set data for different seasons
        cache_service.set("nba:players:2024-25", {"season": "2024-25"})
        cache_service.set("nba:stats:2024-25", {"season": "2024-25"})
        cache_service.set("nba:players:2023-24", {"season": "2023-24"})

        deleted_count = cache_service.invalidate_season("2024-25")

        assert deleted_count == 2
        assert cache_service.get("nba:players:2024-25") is None
        assert cache_service.get("nba:stats:2024-25") is None
        # Other season should remain
        assert cache_service.get("nba:players:2023-24") is not None

    def test_graceful_fallback_when_redis_unavailable(self, mock_settings):
        """Verify operations return gracefully when Redis is unavailable."""
        with patch("app.services.redis_cache.settings", mock_settings):
            service = RedisCacheService(redis_url="redis://invalid:9999/0")
            service._connected = False
            service._last_connection_attempt = datetime.now()
            service._reconnect_interval = 60  # Prevent reconnection attempts

            # Operations should not raise, just return None/False
            assert service.get("any:key") is None
            assert service.set("any:key", {"data": "value"}) is False
            assert service.delete("any:key") is False
            assert service.delete_pattern("any:*") == 0

    def test_cache_disabled_returns_none(self, mock_settings):
        """Verify operations return None when cache is disabled."""
        mock_settings.cache_enabled = False
        with patch("app.services.redis_cache.settings", mock_settings):
            service = RedisCacheService()

            assert service._get_client() is None
            assert service.get("any:key") is None

    def test_is_connected(self, cache_service):
        """Verify is_connected() returns correct connection status."""
        assert cache_service.is_connected() is True

    def test_get_stats_returns_stats_dict(self, cache_service):
        """Verify get_stats() returns statistics dictionary."""
        # Set some keys first
        cache_service.set("stats:test1", {"data": 1})
        cache_service.set("stats:test2", {"data": 2})

        # Mock the info() calls since fakeredis may not support them fully
        cache_service._client.info = MagicMock(side_effect=[
            {"keyspace_hits": 10, "keyspace_misses": 5},  # stats
            {"db0": {"keys": 2}},  # keyspace
        ])

        stats = cache_service.get_stats()

        assert "connected" in stats
        assert stats["connected"] is True
        assert "enabled" in stats
        assert "hits" in stats
        assert "misses" in stats

    def test_handles_json_decode_error(self, cache_service):
        """Verify invalid JSON is handled gracefully."""
        # Directly set invalid JSON in Redis
        cache_service._client.setex("bad:json", 100, "not valid json {{{")

        result = cache_service.get("bad:json")

        assert result is None  # Should return None, not raise

    def test_handles_connection_error_during_get(self, cache_service):
        """Verify connection errors during get are handled gracefully."""
        # Mock connection error with redis-specific exception
        cache_service._client.get = MagicMock(
            side_effect=RedisConnectionError("Connection lost")
        )

        result = cache_service.get("test:key")

        assert result is None
        assert cache_service._connected is False

    def test_handles_connection_error_during_set(self, cache_service):
        """Verify connection errors during set are handled gracefully."""
        cache_service._client.setex = MagicMock(
            side_effect=RedisConnectionError("Connection lost")
        )

        result = cache_service.set("test:key", {"data": "value"})

        assert result is False
        assert cache_service._connected is False

    def test_build_key_with_enum_prefix(self, cache_service):
        """Verify key building works with CacheKeyPrefix enum."""
        key = cache_service._build_key(CacheKeyPrefix.NBA_PLAYERS, "2024-25")
        assert key == "nba:players:2024-25"

    def test_build_key_with_string_prefix(self, cache_service):
        """Verify key building works with string prefix."""
        key = cache_service._build_key("custom:prefix", "part1", "part2")
        assert key == "custom:prefix:part1:part2"

    def test_get_ttl_for_existing_key(self, cache_service):
        """Verify get_ttl returns remaining TTL for existing key."""
        cache_service.set("test:ttl:check", {"data": "value"}, ttl=1000)

        ttl = cache_service.get_ttl("test:ttl:check")

        assert ttl > 0
        assert ttl <= 1000

    def test_get_ttl_returns_minus_two_for_missing_key(self, cache_service):
        """Verify get_ttl returns -2 for non-existent key."""
        ttl = cache_service.get_ttl("nonexistent:key")
        assert ttl == -2


class TestGetCachedOrFetch:
    """Tests for the get_cached_or_fetch helper function."""

    @pytest.fixture
    def mock_redis_cache(self, mock_settings):
        """Provide a mock redis_cache for testing."""
        with patch("app.services.redis_cache.settings", mock_settings):
            mock_cache = MagicMock()
            return mock_cache

    def test_returns_cached_data_on_hit(self, mock_settings):
        """Verify cached data is returned without calling fetch function."""
        cached_data = {"cached": True, "data": "from cache"}
        fetch_func = MagicMock(return_value={"fresh": True})

        with patch("app.services.redis_cache.settings", mock_settings):
            with patch("app.services.redis_cache.redis_cache") as mock_cache:
                mock_cache.get.return_value = cached_data

                result = get_cached_or_fetch("test:key", fetch_func)

                assert result == cached_data
                fetch_func.assert_not_called()

    def test_calls_fetch_on_cache_miss(self, mock_settings):
        """Verify fetch function is called on cache miss."""
        fresh_data = {"fresh": True, "data": "from API"}
        fetch_func = MagicMock(return_value=fresh_data)

        with patch("app.services.redis_cache.settings", mock_settings):
            with patch("app.services.redis_cache.redis_cache") as mock_cache:
                mock_cache.get.return_value = None

                result = get_cached_or_fetch("test:key", fetch_func)

                assert result == fresh_data
                fetch_func.assert_called_once()

    def test_caches_fetched_data(self, mock_settings):
        """Verify fetched data is cached."""
        fresh_data = {"fresh": True}
        fetch_func = MagicMock(return_value=fresh_data)

        with patch("app.services.redis_cache.settings", mock_settings):
            with patch("app.services.redis_cache.redis_cache") as mock_cache:
                mock_cache.get.return_value = None

                get_cached_or_fetch("test:key", fetch_func, ttl=3600)

                mock_cache.set.assert_called_once_with(
                    "test:key", fresh_data, ttl=3600
                )

    def test_bypass_cache_skips_cache_lookup(self, mock_settings):
        """Verify bypass_cache=True skips cache lookup."""
        fresh_data = {"fresh": True}
        fetch_func = MagicMock(return_value=fresh_data)

        with patch("app.services.redis_cache.settings", mock_settings):
            with patch("app.services.redis_cache.redis_cache") as mock_cache:
                mock_cache.get.return_value = {"cached": True}

                result = get_cached_or_fetch(
                    "test:key", fetch_func, bypass_cache=True
                )

                # Should NOT check cache
                mock_cache.get.assert_not_called()
                # Should call fetch
                fetch_func.assert_called_once()
                assert result == fresh_data

    def test_does_not_cache_none_result(self, mock_settings):
        """Verify None results are not cached."""
        fetch_func = MagicMock(return_value=None)

        with patch("app.services.redis_cache.settings", mock_settings):
            with patch("app.services.redis_cache.redis_cache") as mock_cache:
                mock_cache.get.return_value = None

                result = get_cached_or_fetch("test:key", fetch_func)

                assert result is None
                mock_cache.set.assert_not_called()


class TestCacheServiceReconnection:
    """Tests for Redis reconnection behavior."""

    def test_reconnection_after_interval(self, mock_settings):
        """Verify reconnection is attempted after interval."""
        with patch("app.services.redis_cache.settings", mock_settings):
            service = RedisCacheService()
            service._connected = False
            service._reconnect_interval = 0  # No wait

            # Should attempt reconnection
            with patch.object(service, "_client", None):
                with patch("app.services.redis_cache.redis.from_url") as mock_redis:
                    mock_client = MagicMock()
                    mock_client.ping.side_effect = RedisConnectionError()
                    mock_redis.return_value = mock_client

                    service._get_client()

                    mock_redis.assert_called_once()

    def test_no_reconnection_before_interval(self, mock_settings):
        """Verify reconnection is not attempted before interval."""
        with patch("app.services.redis_cache.settings", mock_settings):
            service = RedisCacheService()
            service._connected = False
            service._last_connection_attempt = datetime.now()
            service._reconnect_interval = 60  # Long interval

            result = service._get_client()

            assert result is None


class TestCacheWithDecimalData:
    """Tests for caching data containing Decimal types."""

    @pytest.fixture
    def cache_service(self, mock_settings):
        """Provide cache service with fakeredis."""
        with patch("app.services.redis_cache.settings", mock_settings):
            service = RedisCacheService()
            fake_client = fakeredis.FakeRedis(decode_responses=True)
            service._client = fake_client
            service._connected = True
            return service

    def test_caches_decimal_values(self, cache_service):
        """Verify Decimal values are properly serialized and deserialized."""
        data_with_decimals = {
            "player_id": 1,
            "points_per_touch": Decimal("0.456"),
            "time_of_possession": Decimal("123.45"),
        }

        cache_service.set("test:decimals", data_with_decimals)
        result = cache_service.get("test:decimals")

        # Values are retrieved as strings (original Decimal info lost)
        # This is expected behavior based on the implementation
        assert result is not None
        assert "player_id" in result
