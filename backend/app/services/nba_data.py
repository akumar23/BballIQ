"""Service for fetching data from NBA API and PBP Stats.

This module provides rate-limited, resilient access to the NBA Stats API
with exponential backoff, retry logic, circuit breaker protection, and
Redis caching to minimize external API calls.
"""

import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, TypeVar

from nba_api.stats.endpoints import (
    CommonAllPlayers,
    LeagueDashPlayerStats,
)
from nba_api.stats.endpoints.leaguedashptdefend import LeagueDashPtDefend
from nba_api.stats.endpoints.leaguedashptstats import LeagueDashPtStats
from nba_api.stats.endpoints.leaguehustlestatsplayer import LeagueHustleStatsPlayer

from app.core.config import settings
from app.services.rate_limiter import (
    CircuitBreakerError,
    RateLimitError,
    calculate_backoff_delay,
    get_nba_session,
    nba_api_circuit_breaker,
    with_retry,
)
from app.services.redis_cache import (
    CacheKeyPrefix,
    redis_cache,
)


logger = logging.getLogger(__name__)

# Type variable for endpoint classes
EndpointT = TypeVar("EndpointT")


@dataclass
class PlayerTrackingData:
    """Aggregated tracking data for a player."""

    player_id: int
    player_name: str
    team_abbreviation: str

    # Offensive tracking
    touches: int
    front_court_touches: int
    time_of_possession: Decimal
    avg_seconds_per_touch: Decimal
    avg_dribbles_per_touch: Decimal
    points_per_touch: Decimal

    # Defensive tracking
    deflections: int
    contested_shots_2pt: int
    contested_shots_3pt: int
    charges_drawn: int
    loose_balls_recovered: int

    # Traditional stats for calculations
    points: int
    assists: int
    turnovers: int
    fta: int
    minutes: Decimal


class NBADataService:
    """Fetches tracking and traditional stats from NBA API.

    This service implements robust rate limiting with:
    - Exponential backoff with jitter for retries
    - Circuit breaker to prevent hammering a failing API
    - Configurable retry logic
    - Proper HTTP headers for NBA API authentication
    - Redis caching to minimize external API calls

    Attributes:
        cache_dir: Directory for caching API responses
        max_retries: Maximum retry attempts per request
        base_delay: Base delay between requests in seconds
        bypass_cache: If True, skip cache lookup and force API fetch
    """

    def __init__(
        self,
        max_retries: int | None = None,
        base_delay: float | None = None,
        bypass_cache: bool = False,
    ):
        """Initialize the NBA Data Service.

        Args:
            max_retries: Maximum retry attempts (uses config default if None)
            base_delay: Base delay between requests (uses config default if None)
            bypass_cache: If True, skip Redis cache and always fetch from API
        """
        self.cache_dir = settings.nba_api_cache_dir
        self.max_retries = (
            max_retries if max_retries is not None else settings.nba_api_max_retries
        )
        self.base_delay = (
            base_delay if base_delay is not None else settings.nba_api_base_delay
        )
        self.bypass_cache = bypass_cache
        self._session = get_nba_session()

    def _request_with_retry(
        self,
        endpoint_class: type[EndpointT],
        **kwargs: Any,
    ) -> EndpointT:
        """Make API request with retry logic and proper headers.

        This method wraps NBA API endpoint calls with:
        - Circuit breaker protection
        - Exponential backoff on failures
        - Proper HTTP headers via custom session
        - Comprehensive logging

        Args:
            endpoint_class: The NBA API endpoint class to instantiate
            **kwargs: Arguments to pass to the endpoint

        Returns:
            Instantiated endpoint with data

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
            Exception: For non-retryable errors
        """
        # Check circuit breaker before attempting
        if not nba_api_circuit_breaker.can_execute():
            recovery_time = self._get_circuit_recovery_time()
            raise CircuitBreakerError(
                f"NBA API circuit breaker is open. Recovery in {recovery_time:.1f}s",
                recovery_time,
            )

        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                # Apply delay (base delay for first request, backoff for retries)
                if attempt > 0:
                    delay = calculate_backoff_delay(
                        attempt - 1, base_delay=self.base_delay
                    )
                    endpoint_name = getattr(endpoint_class, "__name__", str(endpoint_class))
                    logger.info(
                        "Retry attempt %d/%d for %s, waiting %.2fs",
                        attempt,
                        self.max_retries,
                        endpoint_name,
                        delay,
                    )
                else:
                    delay = self.base_delay

                time.sleep(delay)

                # Make the API call with custom headers via session
                # The nba_api library accepts custom_headers parameter
                endpoint = endpoint_class(
                    **kwargs,
                    headers=self._session.headers,
                    timeout=settings.nba_api_timeout,
                )

                # Record success
                nba_api_circuit_breaker.record_success()
                endpoint_name = getattr(endpoint_class, "__name__", str(endpoint_class))
                logger.debug(
                    "Successfully fetched %s",
                    endpoint_name,
                )

                return endpoint

            except Exception as e:
                last_exception = e
                error_str = str(e).lower()

                # Check if rate limited (429)
                is_rate_limit = any(
                    indicator in error_str
                    for indicator in ["429", "too many requests", "rate limit"]
                )

                # Check if server error (5xx)
                is_server_error = any(
                    str(code) in str(e) for code in [500, 502, 503, 504]
                )

                endpoint_name = getattr(endpoint_class, "__name__", str(endpoint_class))
                if is_rate_limit or is_server_error:
                    logger.warning(
                        "Request to %s failed (attempt %d/%d): %s",
                        endpoint_name,
                        attempt + 1,
                        self.max_retries + 1,
                        e,
                    )
                    nba_api_circuit_breaker.record_failure()
                    continue
                else:
                    # Non-retryable error
                    logger.error(
                        "Non-retryable error for %s: %s",
                        endpoint_name,
                        e,
                    )
                    nba_api_circuit_breaker.record_failure()
                    raise

        # Max retries exceeded
        nba_api_circuit_breaker.record_failure()

        if last_exception:
            if "429" in str(last_exception) or "rate limit" in str(last_exception).lower():
                raise RateLimitError(
                    f"Rate limited after {self.max_retries + 1} attempts: {last_exception}",
                    retry_after=calculate_backoff_delay(self.max_retries),
                )
            raise last_exception

        raise RuntimeError("Unknown error during retry")

    def _get_circuit_recovery_time(self) -> float:
        """Calculate remaining recovery time for circuit breaker."""
        if nba_api_circuit_breaker._last_failure_time:
            elapsed = time.time() - nba_api_circuit_breaker._last_failure_time
            return max(0, nba_api_circuit_breaker.recovery_timeout - elapsed)
        return 0

    def _get_cache_key(self, prefix: CacheKeyPrefix, season: str) -> str:
        """Build a cache key for the given data type and season.

        Args:
            prefix: Cache key prefix
            season: NBA season string

        Returns:
            Formatted cache key
        """
        return f"{prefix.value}:{season}"

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
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for players (season: %s)", season)
                return cached

        logger.info("Cache miss for players (season: %s), fetching from API", season)
        players = self._request_with_retry(
            CommonAllPlayers,
            is_only_current_season=1,
            season=season,
        )
        result = players.get_normalized_dict()["CommonAllPlayers"]

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_players)
        return result

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
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for traditional stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for traditional stats (season: %s), fetching from API", season
        )
        stats = self._request_with_retry(
            LeagueDashPlayerStats,
            season=season,
            per_mode_detailed="Totals",
            measure_type_detailed_defense="Base",
        )
        result = stats.get_normalized_dict()["LeagueDashPlayerStats"]

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
        return result

    def get_touch_stats(self, season: str = "2024-25") -> list[dict]:
        """Get touch tracking stats for all players.

        Returns: touches, front_court_touches, time_of_possession,
                 avg_sec_per_touch, avg_drib_per_touch, pts_per_touch

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player touch stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_TOUCH_STATS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for touch stats (season: %s)", season)
                return cached

        logger.info("Cache miss for touch stats (season: %s), fetching from API", season)
        touches = self._request_with_retry(
            LeagueDashPtStats,
            season=season,
            per_mode_simple="Totals",
            player_or_team="Player",
            pt_measure_type="Possessions",
        )
        result = touches.get_normalized_dict()["LeagueDashPtStats"]

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
        return result

    def get_hustle_stats(self, season: str = "2024-25") -> list[dict]:
        """Get hustle stats for all players.

        Returns: deflections, contested_shots, charges_drawn,
                 loose_balls_recovered, box_outs

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player hustle stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_HUSTLE_STATS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for hustle stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for hustle stats (season: %s), fetching from API", season
        )
        hustle = self._request_with_retry(
            LeagueHustleStatsPlayer,
            season=season,
            per_mode_time="Totals",
        )
        result = hustle.get_normalized_dict()["HustleStatsPlayer"]

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
        return result

    def get_defensive_stats(self, season: str = "2024-25") -> list[dict]:
        """Get defensive tracking stats for all players.

        Returns: dfg%, contested_2pt, contested_3pt

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player defensive stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_DEFENSIVE_STATS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for defensive stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for defensive stats (season: %s), fetching from API", season
        )
        defense = self._request_with_retry(
            LeagueDashPtDefend,
            season=season,
            per_mode_simple="Totals",
            defense_category="Overall",
        )
        result = defense.get_normalized_dict()["LeagueDashPTDefend"]

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
        return result

    def fetch_all_tracking_data(
        self,
        season: str = "2024-25",
    ) -> dict[int, PlayerTrackingData]:
        """Fetch and combine all tracking data for all players.

        This method fetches data from multiple endpoints and combines them
        into PlayerTrackingData objects. It handles errors gracefully and
        logs progress.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            Dict keyed by player_id with aggregated PlayerTrackingData

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        logger.info("Fetching tracking data for season %s...", season)
        print(f"Fetching tracking data for season {season}...")

        # Fetch all data sources with proper error handling
        logger.info("Fetching traditional stats...")
        print("  - Fetching traditional stats...")
        traditional = {p["PLAYER_ID"]: p for p in self.get_traditional_stats(season)}

        logger.info("Fetching touch stats...")
        print("  - Fetching touch stats...")
        touches = {p["PLAYER_ID"]: p for p in self.get_touch_stats(season)}

        logger.info("Fetching hustle stats...")
        print("  - Fetching hustle stats...")
        hustle = {p["PLAYER_ID"]: p for p in self.get_hustle_stats(season)}

        logger.info("Fetching defensive stats...")
        print("  - Fetching defensive stats...")
        defense = {p["CLOSE_DEF_PERSON_ID"]: p for p in self.get_defensive_stats(season)}

        # Combine into PlayerTrackingData objects
        combined: dict[int, PlayerTrackingData] = {}

        for player_id, trad in traditional.items():
            touch = touches.get(player_id, {})
            hust = hustle.get(player_id, {})
            defn = defense.get(player_id, {})

            # Skip players with no touch data
            if not touch.get("TOUCHES"):
                continue

            combined[player_id] = PlayerTrackingData(
                player_id=player_id,
                player_name=trad.get("PLAYER_NAME", ""),
                team_abbreviation=trad.get("TEAM_ABBREVIATION", ""),
                # Offensive tracking
                touches=touch.get("TOUCHES", 0) or 0,
                front_court_touches=touch.get("FRONT_CT_TOUCHES", 0) or 0,
                time_of_possession=Decimal(str(touch.get("TIME_OF_POSS", 0) or 0)),
                avg_seconds_per_touch=Decimal(
                    str(touch.get("AVG_SEC_PER_TOUCH", 0) or 0)
                ),
                avg_dribbles_per_touch=Decimal(
                    str(touch.get("AVG_DRIB_PER_TOUCH", 0) or 0)
                ),
                points_per_touch=Decimal(str(touch.get("PTS_PER_TOUCH", 0) or 0)),
                # Defensive tracking (from hustle stats)
                deflections=hust.get("DEFLECTIONS", 0) or 0,
                contested_shots_2pt=hust.get("CONTESTED_SHOTS_2PT", 0) or 0,
                contested_shots_3pt=hust.get("CONTESTED_SHOTS_3PT", 0) or 0,
                charges_drawn=hust.get("CHARGES_DRAWN", 0) or 0,
                loose_balls_recovered=hust.get("LOOSE_BALLS_RECOVERED", 0) or 0,
                # Traditional stats
                points=trad.get("PTS", 0) or 0,
                assists=trad.get("AST", 0) or 0,
                turnovers=trad.get("TOV", 0) or 0,
                fta=trad.get("FTA", 0) or 0,
                minutes=Decimal(str(trad.get("MIN", 0) or 0)),
            )

        logger.info("Combined data for %d players", len(combined))
        print(f"  - Combined data for {len(combined)} players")
        return combined


# Singleton instance
nba_data_service = NBADataService()
