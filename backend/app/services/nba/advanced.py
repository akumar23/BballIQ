"""Advanced and clutch stat fetchers."""

from __future__ import annotations

import logging

from app.services import nba_data as _nd
from app.services.redis_cache import CacheKeyPrefix

logger = logging.getLogger(__name__)


class AdvancedMixin:
    """Advanced (pace/ratings/PIE) and clutch-time stat fetchers."""

    def get_advanced_stats(self, season: str = "2024-25") -> list[dict]:
        """Get advanced stats for all players.

        Returns: TS%, USG%, ORtg, DRtg, PACE, PIE, EFG%, AST%, AST_TO,
                 AST_RATIO, OREB%, DREB%, REB%, TM_TOV%

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player advanced stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_ADVANCED_STATS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for advanced stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for advanced stats (season: %s), fetching from API", season
        )
        stats = self._request_with_retry(
            _nd.LeagueDashPlayerStats,
            season=season,
            per_mode_detailed="PerGame",
            measure_type_detailed_defense="Advanced",
        )
        result = stats.get_normalized_dict()["LeagueDashPlayerStats"]

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_clutch_stats(self, season: str = "2024-25") -> list[dict]:
        """Get clutch time stats for all players.

        Clutch is defined as the last 5 minutes of a game when the score
        differential is 5 points or fewer.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player clutch stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_CLUTCH_STATS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for clutch stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for clutch stats (season: %s), fetching from API", season
        )
        clutch = self._request_with_retry(
            _nd.LeagueDashPlayerClutch,
            season=season,
            ahead_behind="Ahead or Behind",
            clutch_time="Last 5 Minutes",
            point_diff=5,
            per_mode_detailed="PerGame",
            measure_type_detailed_defense="Base",
        )
        result = clutch.get_normalized_dict().get("LeagueDashPlayerClutch", [])

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result
