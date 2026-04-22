"""Shared state and HTTP-retry plumbing for the NBA API client.

All per-family mixins depend on the helpers declared here via ``self``:

- :meth:`_request_with_retry` — exponential-backoff wrapper with circuit breaker
  integration around a raw ``nba_api`` endpoint class.
- :meth:`_get_cache_key` — builds the Redis cache key for a given season.
- :meth:`_get_pt_measure_stats` — shared fetcher used by the elbow/post/paint
  touch endpoints which all hit the same underlying endpoint with a different
  ``pt_measure_type`` parameter.

Patchable module-level names (``settings``, ``get_nba_session``,
``nba_api_circuit_breaker``, ``redis_cache``, and the endpoint classes) are
resolved through ``app.services.nba_data`` at call time so that existing
``unittest.mock.patch("app.services.nba_data.<name>", ...)`` sites keep working
after the split.
"""

from __future__ import annotations

import logging
import time
from typing import Any, TypeVar

from app.services import nba_data as _nd
from app.services.rate_limiter import (
    CircuitBreakerError,
    RateLimitError,
    calculate_backoff_delay,
)
from app.services.redis_cache import CacheKeyPrefix

logger = logging.getLogger(__name__)

# Type variable for endpoint classes
EndpointT = TypeVar("EndpointT")


class BaseNBAClient:
    """Core client state + retry/cache plumbing shared by every mixin.

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
        self.cache_dir = _nd.settings.nba_api_cache_dir
        self.max_retries = (
            max_retries if max_retries is not None else _nd.settings.nba_api_max_retries
        )
        self.base_delay = (
            base_delay if base_delay is not None else _nd.settings.nba_api_base_delay
        )
        self.bypass_cache = bypass_cache
        self._session = _nd.get_nba_session()

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
        if not _nd.nba_api_circuit_breaker.can_execute():
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

                # Make the API call
                # Note: We don't pass custom headers - the nba_api library
                # has well-configured defaults (STATS_HEADERS) that work better
                # Passing custom headers can cause timeout issues
                endpoint = endpoint_class(
                    **kwargs,
                    timeout=_nd.settings.nba_api_timeout,
                )

                # Record success
                _nd.nba_api_circuit_breaker.record_success()
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

                # Check if timeout error (should retry)
                is_timeout = any(
                    indicator in error_str
                    for indicator in ["timeout", "timed out", "read timed out"]
                )

                # Check if connection error (should retry)
                is_connection_error = any(
                    indicator in error_str
                    for indicator in [
                        "connection reset",
                        "connection aborted",
                        "connection refused",
                        "broken pipe",
                        "connectionreseterror",
                    ]
                )

                endpoint_name = getattr(endpoint_class, "__name__", str(endpoint_class))
                if is_rate_limit or is_server_error or is_timeout or is_connection_error:
                    logger.warning(
                        "Request to %s failed (attempt %d/%d): %s",
                        endpoint_name,
                        attempt + 1,
                        self.max_retries + 1,
                        e,
                    )
                    _nd.nba_api_circuit_breaker.record_failure()
                    continue
                else:
                    # Non-retryable error
                    logger.error(
                        "Non-retryable error for %s: %s",
                        endpoint_name,
                        e,
                    )
                    _nd.nba_api_circuit_breaker.record_failure()
                    raise

        # Max retries exceeded
        _nd.nba_api_circuit_breaker.record_failure()

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
        if _nd.nba_api_circuit_breaker._last_failure_time:
            elapsed = time.time() - _nd.nba_api_circuit_breaker._last_failure_time
            return max(0, _nd.nba_api_circuit_breaker.recovery_timeout - elapsed)
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

    def _get_pt_measure_stats(
        self,
        measure_type: str,
        cache_prefix: CacheKeyPrefix,
        season: str,
    ) -> list[dict]:
        """Shared fetcher for LeagueDashPtStats measure-type variants.

        Used by the elbow/post/paint touch breakdown endpoints which all hit
        the same underlying endpoint with a different pt_measure_type.
        """
        cache_key = self._get_cache_key(cache_prefix, season)

        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info(
                    "Cache hit for %s stats (season: %s)", measure_type, season
                )
                return cached

        logger.info(
            "Cache miss for %s stats (season: %s), fetching from API",
            measure_type,
            season,
        )
        stats = self._request_with_retry(
            _nd.LeagueDashPtStats,
            season=season,
            per_mode_simple="PerGame",
            player_or_team="Player",
            pt_measure_type=measure_type,
        )
        result = stats.get_normalized_dict()["LeagueDashPtStats"]

        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result
