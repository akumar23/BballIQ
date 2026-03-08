"""Service for fetching data from PBP Stats.

This module provides rate-limited, resilient access to the PBP Stats API
with exponential backoff, retry logic, circuit breaker protection, and
Redis caching to minimize external API calls.
"""

import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any

from pbpstats.client import Client
from pbpstats.resources.enhanced_pbp import EnhancedPbpItem

from app.core.config import settings
from app.services.rate_limiter import (
    CircuitBreaker,
    CircuitBreakerError,
    RateLimitError,
    calculate_backoff_delay,
    is_rate_limit_error,
    is_server_error,
)
from app.services.redis_cache import (
    CacheKeyPrefix,
    redis_cache,
)


logger = logging.getLogger(__name__)


# Circuit breaker for PBP Stats API
pbp_stats_circuit_breaker = CircuitBreaker(name="pbp_stats")


@dataclass
class PossessionStats:
    """Possession-level stats for a player."""

    player_id: int
    player_name: str

    # Offensive possessions
    total_possessions: int
    points_per_possession: Decimal
    turnover_rate: Decimal
    assist_rate: Decimal

    # Play type breakdown (possessions)
    isolation_poss: int
    pnr_ball_handler_poss: int
    pnr_roll_man_poss: int
    post_up_poss: int
    spot_up_poss: int
    transition_poss: int
    cut_poss: int


class PBPStatsService:
    """Fetches play-by-play derived stats from pbpstats.

    This service implements robust rate limiting with:
    - Exponential backoff with jitter for retries
    - Circuit breaker to prevent hammering a failing API
    - Configurable retry logic
    - Comprehensive logging
    - Redis caching to minimize external API calls

    Attributes:
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
        """Initialize the PBP Stats Service.

        Args:
            max_retries: Maximum retry attempts (uses config default if None)
            base_delay: Base delay between requests (uses config default if None)
            bypass_cache: If True, skip Redis cache and always fetch from API
        """
        self.max_retries = (
            max_retries if max_retries is not None else settings.nba_api_max_retries
        )
        self.base_delay = (
            base_delay if base_delay is not None else settings.nba_api_base_delay
        )
        self.bypass_cache = bypass_cache
        self._settings = {
            "dir": settings.nba_api_cache_dir,
            "Boxscore": {"source": "file", "data_provider": "stats_nba"},
            "Possessions": {"source": "file", "data_provider": "stats_nba"},
        }

    def _get_circuit_recovery_time(self) -> float:
        """Calculate remaining recovery time for circuit breaker."""
        if pbp_stats_circuit_breaker._last_failure_time:
            elapsed = time.time() - pbp_stats_circuit_breaker._last_failure_time
            return max(0, pbp_stats_circuit_breaker.recovery_timeout - elapsed)
        return 0

    def _execute_with_retry(
        self,
        operation: str,
        func: callable,
        *args: Any,
        **kwargs: Any,
    ) -> Any:
        """Execute a function with retry logic and circuit breaker protection.

        Args:
            operation: Description of the operation for logging
            func: Function to execute
            *args: Positional arguments for func
            **kwargs: Keyword arguments for func

        Returns:
            Result of func(*args, **kwargs)

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
            Exception: For non-retryable errors
        """
        # Check circuit breaker
        if not pbp_stats_circuit_breaker.can_execute():
            recovery_time = self._get_circuit_recovery_time()
            raise CircuitBreakerError(
                f"PBP Stats circuit breaker is open. Recovery in {recovery_time:.1f}s",
                recovery_time,
            )

        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                # Apply delay
                if attempt > 0:
                    delay = calculate_backoff_delay(
                        attempt - 1, base_delay=self.base_delay
                    )
                    logger.info(
                        "Retry attempt %d/%d for %s, waiting %.2fs",
                        attempt,
                        self.max_retries,
                        operation,
                        delay,
                    )
                else:
                    delay = self.base_delay

                time.sleep(delay)

                # Execute the operation
                result = func(*args, **kwargs)

                # Record success
                pbp_stats_circuit_breaker.record_success()
                logger.debug("Successfully executed %s", operation)

                return result

            except Exception as e:
                last_exception = e

                if is_rate_limit_error(e) or is_server_error(e):
                    logger.warning(
                        "%s failed (attempt %d/%d): %s",
                        operation,
                        attempt + 1,
                        self.max_retries + 1,
                        e,
                    )
                    pbp_stats_circuit_breaker.record_failure()
                    continue
                else:
                    # Non-retryable error
                    logger.error("Non-retryable error for %s: %s", operation, e)
                    pbp_stats_circuit_breaker.record_failure()
                    raise

        # Max retries exceeded
        pbp_stats_circuit_breaker.record_failure()

        if last_exception:
            if is_rate_limit_error(last_exception):
                raise RateLimitError(
                    f"Rate limited after {self.max_retries + 1} attempts: {last_exception}",
                    retry_after=calculate_backoff_delay(self.max_retries),
                )
            raise last_exception

        raise RuntimeError("Unknown error during retry")

    def get_client(self) -> Client:
        """Get configured pbpstats client.

        Returns:
            Configured pbpstats Client instance
        """
        return Client(self._settings)

    def _get_cache_key(self, prefix: CacheKeyPrefix, *parts: str) -> str:
        """Build a cache key for the given data type.

        Args:
            prefix: Cache key prefix
            *parts: Additional key parts

        Returns:
            Formatted cache key
        """
        all_parts = [prefix.value] + list(parts)
        return ":".join(all_parts)

    def get_season_totals(
        self,
        season: str = "2024-25",
        season_type: str = "Regular Season",
    ) -> dict:
        """Get season totals for all players.

        Note: This requires having cached game data locally.
        For initial setup, you need to fetch games first.

        Args:
            season: NBA season string (e.g., "2024-25")
            season_type: "Regular Season" or "Playoffs"

        Returns:
            Dictionary containing games data

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        # Normalize season_type for cache key
        season_type_key = season_type.lower().replace(" ", "_")
        cache_key = self._get_cache_key(
            CacheKeyPrefix.PBP_SEASON_TOTALS, season, season_type_key
        )

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info(
                    "Cache hit for season totals (season: %s, type: %s)",
                    season,
                    season_type,
                )
                return cached

        logger.info(
            "Cache miss for season totals (season: %s, type: %s), fetching from API",
            season,
            season_type,
        )

        def _fetch_season() -> dict:
            client = Client(
                {"Games": {"source": "web", "data_provider": "data_nba"}}
            )
            season_obj = client.Season("nba", season, season_type)
            return {"games": [g for g in season_obj.games.items]}

        try:
            result = self._execute_with_retry(
                f"fetch_season_{season}_{season_type}",
                _fetch_season,
            )

            # Cache the result
            redis_cache.set(
                cache_key, result, ttl=settings.cache_ttl_tracking_stats
            )
            return result
        except CircuitBreakerError:
            raise
        except RateLimitError:
            raise
        except Exception as e:
            logger.error("Error fetching season data: %s", e)
            return {"games": []}

    def get_game_possessions(self, game_id: str) -> list:
        """Get all possessions for a specific game.

        Args:
            game_id: NBA game ID string

        Returns:
            List of possession items

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(
            CacheKeyPrefix.PBP_GAME_POSSESSIONS, game_id
        )

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.debug("Cache hit for game possessions (game_id: %s)", game_id)
                return cached

        logger.debug(
            "Cache miss for game possessions (game_id: %s), fetching from API",
            game_id,
        )

        def _fetch_possessions() -> list:
            client = self.get_client()
            game = client.Game(game_id)
            return list(game.possessions.items)

        try:
            result = self._execute_with_retry(
                f"fetch_game_possessions_{game_id}",
                _fetch_possessions,
            )

            # Cache the result (game data is historical, use longer TTL)
            redis_cache.set(
                cache_key, result, ttl=settings.cache_ttl_game_possessions
            )
            return result
        except CircuitBreakerError:
            raise
        except RateLimitError:
            raise
        except Exception as e:
            logger.error("Error fetching game %s: %s", game_id, e)
            return []

    def get_multiple_game_possessions(
        self,
        game_ids: list[str],
        on_progress: callable | None = None,
    ) -> dict[str, list]:
        """Fetch possessions for multiple games with proper rate limiting.

        This method handles batch fetching with:
        - Proper delays between requests
        - Error recovery and continuation
        - Progress reporting

        Args:
            game_ids: List of NBA game ID strings
            on_progress: Optional callback with (completed, total, game_id)

        Returns:
            Dictionary mapping game_id to list of possessions

        Raises:
            CircuitBreakerError: If circuit breaker is open and cannot recover
        """
        results: dict[str, list] = {}
        failed_games: list[str] = []

        for i, game_id in enumerate(game_ids):
            try:
                possessions = self.get_game_possessions(game_id)
                results[game_id] = possessions

                if on_progress:
                    on_progress(i + 1, len(game_ids), game_id)

            except CircuitBreakerError as e:
                logger.warning(
                    "Circuit breaker open, waiting for recovery. "
                    "Failed at game %d/%d (%s)",
                    i + 1,
                    len(game_ids),
                    game_id,
                )
                # Wait for recovery and retry
                time.sleep(e.recovery_time + 1)

                # Retry this game
                try:
                    possessions = self.get_game_possessions(game_id)
                    results[game_id] = possessions
                except Exception:
                    failed_games.append(game_id)

            except RateLimitError as e:
                logger.warning(
                    "Rate limited on game %s. Waiting %.1fs before continuing",
                    game_id,
                    e.retry_after or 60,
                )
                failed_games.append(game_id)
                time.sleep(e.retry_after or 60)

            except Exception as e:
                logger.error("Failed to fetch game %s: %s", game_id, e)
                failed_games.append(game_id)

        if failed_games:
            logger.warning(
                "Failed to fetch %d games: %s",
                len(failed_games),
                failed_games[:10],  # Log first 10
            )

        return results


# Singleton instance
pbp_stats_service = PBPStatsService()
