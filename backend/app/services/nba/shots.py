"""Shot-location and league-wide shot-average fetchers."""

from __future__ import annotations

import logging

from app.services import nba_data as _nd
from app.services.redis_cache import CacheKeyPrefix

logger = logging.getLogger(__name__)


class ShotsMixin:
    """Shot location and league-wide shot average fetchers."""

    def get_shot_location_stats(self, season: str = "2024-25") -> list[dict]:
        """Get shot location stats (by zone) for all players.

        Returns per-zone FGM, FGA, FG_PCT for: Restricted Area, In The Paint
        (Non-RA), Mid-Range, Left Corner 3, Right Corner 3, Above the Break 3,
        Backcourt.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player shot location stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_SHOT_LOCATIONS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for shot location stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for shot location stats (season: %s), fetching from API",
            season,
        )
        shots = self._request_with_retry(
            _nd.LeagueDashPlayerShotLocations,
            season=season,
            distance_range="By Zone",
            per_mode_detailed="PerGame",
        )
        # get_normalized_dict() fails when the API returns nested column headers
        # (unhashable type: 'dict'). Use get_data_frames() which is more robust.
        try:
            dfs = shots.get_data_frames()
            result = dfs[0].to_dict("records") if dfs else []
        except Exception:
            result = shots.get_normalized_dict().get("ShotLocations", [])

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_league_shot_averages(self, season: str = "2024-25") -> list[dict]:
        """Get league-wide average FG% by shot zone.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of league shot average dictionaries by zone

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(
            CacheKeyPrefix.NBA_LEAGUE_SHOT_AVERAGES, season
        )

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info(
                    "Cache hit for league shot averages (season: %s)", season
                )
                return cached

        logger.info(
            "Cache miss for league shot averages (season: %s), fetching from API",
            season,
        )
        averages = self._request_with_retry(
            _nd.ShotChartLeagueWide,
            season=season,
        )
        result = averages.get_normalized_dict().get("LeagueWide", [])

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result
