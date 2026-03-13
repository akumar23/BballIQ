"""Services module for CourtVision.

This module provides:
- NBA API data fetching with rate limiting
- PBP Stats data fetching
- Rate limiting utilities (circuit breaker, backoff, retry)
- Redis caching for API responses
- Metrics calculation
"""

from app.services.rate_limiter import (
    CircuitBreaker,
    CircuitBreakerError,
    CircuitState,
    RateLimitError,
    calculate_backoff_delay,
    create_nba_session,
    get_nba_session,
    is_rate_limit_error,
    is_server_error,
    nba_api_circuit_breaker,
    reset_nba_session,
    with_retry,
)
from app.services.nba_data import (
    NBADataService,
    PlayerTrackingData,
    nba_data_service,
)
from app.services.pbp_data import (
    PBPStatsService,
    PossessionStats,
    pbp_stats_circuit_breaker,
    pbp_stats_service,
)
from app.services.redis_cache import (
    CacheKeyPrefix,
    RedisCacheService,
    get_cached_or_fetch,
    redis_cache,
)

__all__ = [
    # Rate limiter
    "CircuitBreaker",
    "CircuitBreakerError",
    "CircuitState",
    "RateLimitError",
    "calculate_backoff_delay",
    "create_nba_session",
    "get_nba_session",
    "is_rate_limit_error",
    "is_server_error",
    "nba_api_circuit_breaker",
    "reset_nba_session",
    "with_retry",
    # NBA Data
    "NBADataService",
    "PlayerTrackingData",
    "nba_data_service",
    # PBP Data
    "PBPStatsService",
    "PossessionStats",
    "pbp_stats_circuit_breaker",
    "pbp_stats_service",
    # Redis Cache
    "CacheKeyPrefix",
    "RedisCacheService",
    "get_cached_or_fetch",
    "redis_cache",
]
