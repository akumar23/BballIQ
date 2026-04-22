"""Player/team roster and biographical data fetchers."""

from __future__ import annotations

import logging

from app.services import nba_data as _nd
from app.services.redis_cache import CacheKeyPrefix

logger = logging.getLogger(__name__)


class PlayersMixin:
    """Roster, team-level, bio, and career stat fetchers."""

    def get_all_players(self, season: str = "2024-25") -> list[dict]:
        """Get all active players for a season.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player dictionaries with player info

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_PLAYERS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for players (season: %s)", season)
                return cached

        logger.info("Cache miss for players (season: %s), fetching from API", season)
        players = self._request_with_retry(
            _nd.CommonAllPlayers,
            is_only_current_season=1,
            season=season,
        )
        result = players.get_normalized_dict()["CommonAllPlayers"]

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_players)
        return result

    def get_team_stats(
        self, season: str = "2024-25", measure_type: str = "Base"
    ) -> list[dict]:
        """Get team-level stats for all teams.

        Args:
            season: NBA season string (e.g., "2024-25")
            measure_type: Stat category - "Base" for traditional totals,
                          "Advanced" for pace/ratings

        Returns:
            List of team stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = f"{CacheKeyPrefix.NBA_TEAM_STATS.value}:{measure_type}:{season}"

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info(
                    "Cache hit for team stats (measure: %s, season: %s)",
                    measure_type,
                    season,
                )
                return cached

        logger.info(
            "Cache miss for team stats (measure: %s, season: %s), fetching from API",
            measure_type,
            season,
        )
        stats = self._request_with_retry(
            _nd.LeagueDashTeamStats,
            season=season,
            per_mode_detailed="Totals",
            measure_type_detailed_defense=measure_type,
        )
        result = stats.get_normalized_dict()["LeagueDashTeamStats"]

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_player_bio_stats(self, season: str = "2024-25") -> list[dict]:
        """Get bio data (height, weight, age, country, draft) for all players.

        Uses LeagueDashPlayerBioStats for a single bulk call.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player bio stat dictionaries with keys:
            PLAYER_ID, PLAYER_NAME, PLAYER_HEIGHT, PLAYER_WEIGHT,
            AGE, COUNTRY, DRAFT_YEAR, DRAFT_ROUND, DRAFT_NUMBER, etc.
        """
        cache_key = f"{CacheKeyPrefix.NBA_PLAYERS.value}:bio:{season}"

        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for player bio stats (season: %s)", season)
                return cached

        logger.info("Cache miss for player bio stats (season: %s), fetching from API", season)
        stats = self._request_with_retry(
            _nd.LeagueDashPlayerBioStats,
            season=season,
        )
        result = stats.get_normalized_dict()["LeagueDashPlayerBioStats"]

        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_players)
        return result

    def get_career_stats(self, player_id: int) -> dict:
        """Get career stats for a single player.

        Returns multiple datasets including SeasonTotalsRegularSeason
        and CareerTotalsRegularSeason.

        Args:
            player_id: NBA player ID

        Returns:
            Dictionary with dataset names as keys and list of row dicts as values

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = f"{CacheKeyPrefix.NBA_CAREER_STATS.value}:{player_id}"

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for career stats (player: %d)", player_id)
                return cached

        logger.info(
            "Cache miss for career stats (player: %d), fetching from API", player_id
        )
        career = self._request_with_retry(
            _nd.PlayerCareerStats,
            player_id=player_id,
            per_mode36="PerGame",
        )
        result = career.get_normalized_dict()

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result
