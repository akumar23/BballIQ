"""Traditional box-score, per-100, and game-log fetchers."""

from __future__ import annotations

import logging

from app.services import nba_data as _nd
from app.services.redis_cache import CacheKeyPrefix

logger = logging.getLogger(__name__)


class TraditionalMixin:
    """Traditional box-score, per-100, and per-game-log fetchers."""

    def get_traditional_stats(self, season: str = "2024-25") -> list[dict]:
        """Get traditional box score stats for all players.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_TRADITIONAL_STATS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for traditional stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for traditional stats (season: %s), fetching from API", season
        )
        stats = self._request_with_retry(
            _nd.LeagueDashPlayerStats,
            season=season,
            per_mode_detailed="Totals",
            measure_type_detailed_defense="Base",
        )
        result = stats.get_normalized_dict()["LeagueDashPlayerStats"]

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_player_game_logs(self, season: str = "2024-25") -> list[dict]:
        """Get all player game logs for a season (bulk, single API call).

        Returns ~30K rows — one row per player per game.
        """
        cache_key = f"{CacheKeyPrefix.NBA_TRACKING_DATA.value}:game_logs:{season}"
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                return cached

        logger.info("Fetching player game logs for season %s", season)
        logs = self._request_with_retry(
            _nd.PlayerGameLogs,
            season_nullable=season,
        )
        result = logs.get_normalized_dict()["PlayerGameLogs"]
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_per100_stats(self, season: str = "2024-25") -> list[dict]:
        """Get per-100 possessions stats for all players.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player per-100 possession stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_PER100_STATS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for per-100 stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for per-100 stats (season: %s), fetching from API", season
        )
        stats = self._request_with_retry(
            _nd.LeagueDashPlayerStats,
            season=season,
            per_mode_detailed="Per100Possessions",
            measure_type_detailed_defense="Base",
        )
        result = stats.get_normalized_dict()["LeagueDashPlayerStats"]

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result
