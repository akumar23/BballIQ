"""Rate limiting utilities for external API calls.

This module provides:
- Exponential backoff with jitter for retry logic
- Circuit breaker pattern for failing fast
- Custom requests session with proper headers
"""

import logging
import random
import threading
import time
from dataclasses import dataclass, field
from enum import Enum

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from app.core.config import settings

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing fast, rejecting requests
    HALF_OPEN = "half_open"  # Testing if service recovered


class RateLimitError(Exception):
    """Raised when rate limited by external API."""

    def __init__(self, message: str, retry_after: float | None = None):
        super().__init__(message)
        self.retry_after = retry_after


class CircuitBreakerError(Exception):
    """Raised when circuit breaker is open."""

    def __init__(self, message: str, recovery_time: float):
        super().__init__(message)
        self.recovery_time = recovery_time


@dataclass
class CircuitBreaker:
    """Circuit breaker pattern implementation for external API calls.

    The circuit breaker prevents repeated calls to a failing service:
    - CLOSED: Normal operation, requests pass through
    - OPEN: Service is failing, requests are rejected immediately
    - HALF_OPEN: Testing if service recovered, limited requests allowed

    Attributes:
        name: Identifier for this circuit breaker (for logging)
        failure_threshold: Number of failures before opening circuit
        recovery_timeout: Seconds to wait before attempting recovery
        half_open_max_calls: Maximum calls allowed in half-open state
    """

    name: str
    failure_threshold: int = field(
        default_factory=lambda: settings.circuit_breaker_failure_threshold
    )
    recovery_timeout: float = field(
        default_factory=lambda: settings.circuit_breaker_recovery_timeout
    )
    half_open_max_calls: int = field(
        default_factory=lambda: settings.circuit_breaker_half_open_max_calls
    )

    # Internal state
    _state: CircuitState = field(default=CircuitState.CLOSED, init=False)
    _failure_count: int = field(default=0, init=False)
    _success_count: int = field(default=0, init=False)
    _last_failure_time: float | None = field(default=None, init=False)
    _half_open_calls: int = field(default=0, init=False)
    _lock: threading.Lock = field(default_factory=threading.Lock, init=False)

    @property
    def state(self) -> CircuitState:
        """Get current circuit state, checking for recovery timeout."""
        with self._lock:
            if self._state == CircuitState.OPEN:
                if self._should_attempt_recovery():
                    self._transition_to_half_open()
            return self._state

    def _should_attempt_recovery(self) -> bool:
        """Check if enough time has passed to attempt recovery."""
        if self._last_failure_time is None:
            return True
        elapsed = time.time() - self._last_failure_time
        return elapsed >= self.recovery_timeout

    def _transition_to_half_open(self) -> None:
        """Transition to half-open state for recovery testing."""
        self._state = CircuitState.HALF_OPEN
        self._half_open_calls = 0
        self._success_count = 0
        logger.info(
            "Circuit breaker '%s' transitioned to HALF_OPEN state",
            self.name,
        )

    def can_execute(self) -> bool:
        """Check if a request can be executed."""
        state = self.state  # This may trigger state transition

        if state == CircuitState.CLOSED:
            return True

        if state == CircuitState.OPEN:
            return False

        # HALF_OPEN: Allow limited calls
        with self._lock:
            if self._half_open_calls < self.half_open_max_calls:
                self._half_open_calls += 1
                return True
            return False

    def record_success(self) -> None:
        """Record a successful call."""
        with self._lock:
            if self._state == CircuitState.HALF_OPEN:
                self._success_count += 1
                # If enough successes in half-open, close the circuit
                if self._success_count >= self.half_open_max_calls:
                    self._state = CircuitState.CLOSED
                    self._failure_count = 0
                    self._success_count = 0
                    logger.info(
                        "Circuit breaker '%s' recovered, now CLOSED",
                        self.name,
                    )
            elif self._state == CircuitState.CLOSED:
                # Reset failure count on success
                self._failure_count = 0

    def record_failure(self) -> None:
        """Record a failed call."""
        with self._lock:
            self._failure_count += 1
            self._last_failure_time = time.time()

            if self._state == CircuitState.HALF_OPEN:
                # Any failure in half-open reopens the circuit
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker '%s' reopened due to failure in HALF_OPEN",
                    self.name,
                )
            elif (
                self._state == CircuitState.CLOSED
                and self._failure_count >= self.failure_threshold
            ):
                self._state = CircuitState.OPEN
                logger.warning(
                    "Circuit breaker '%s' opened after %d failures",
                    self.name,
                    self._failure_count,
                )

    def reset(self) -> None:
        """Reset the circuit breaker to closed state."""
        with self._lock:
            self._state = CircuitState.CLOSED
            self._failure_count = 0
            self._success_count = 0
            self._last_failure_time = None
            self._half_open_calls = 0
            logger.info("Circuit breaker '%s' manually reset", self.name)


def calculate_backoff_delay(
    attempt: int,
    base_delay: float | None = None,
    backoff_base: float | None = None,
    max_delay: float | None = None,
    jitter_max: float | None = None,
) -> float:
    """Calculate exponential backoff delay with jitter.

    Args:
        attempt: Current retry attempt number (0-indexed)
        base_delay: Initial delay in seconds
        backoff_base: Exponential multiplier
        max_delay: Maximum delay cap in seconds
        jitter_max: Maximum jitter factor (0-1)

    Returns:
        Calculated delay in seconds with jitter applied
    """
    base_delay = base_delay if base_delay is not None else settings.nba_api_base_delay
    backoff_base = backoff_base if backoff_base is not None else settings.nba_api_backoff_base
    max_delay = max_delay if max_delay is not None else settings.nba_api_backoff_max
    jitter_max = jitter_max if jitter_max is not None else settings.nba_api_jitter_max

    # Calculate exponential delay
    delay = base_delay * (backoff_base**attempt)

    # Apply cap
    delay = min(delay, max_delay)

    # Add jitter (random factor between 0 and jitter_max of the delay)
    jitter = delay * random.uniform(0, jitter_max)
    delay += jitter

    return delay


def create_nba_session(timeout: int | None = None) -> requests.Session:
    """Create a requests session with NBA API headers and retry configuration.

    Args:
        timeout: Request timeout in seconds (uses settings default if None)

    Returns:
        Configured requests.Session with proper headers
    """
    timeout = timeout or settings.nba_api_timeout

    session = requests.Session()

    # Set NBA API headers
    # Note: We explicitly set Accept-Encoding to gzip,deflate (no zstd)
    # because zstd encoding causes timeouts with the NBA API
    session.headers.update(
        {
            "User-Agent": (
                "Mozilla/5.0 (Windows NT 10.0; Win64; x64) "
                "AppleWebKit/537.36 (KHTML, like Gecko) "
                "Chrome/120.0.0.0 Safari/537.36"
            ),
            "Referer": "https://www.nba.com/",
            "Accept-Language": "en-US,en;q=0.9",
            "Accept": "application/json, text/plain, */*",
            "Accept-Encoding": "gzip, deflate",  # Explicitly set - no zstd
            "Origin": "https://www.nba.com",
            "Connection": "keep-alive",
            "x-nba-stats-origin": "stats",
            "x-nba-stats-token": "true",
        }
    )

    # Configure retry adapter for transport-level errors
    # Note: This handles connection errors, not application-level rate limits
    retry_strategy = Retry(
        total=3,
        backoff_factor=0.5,
        status_forcelist=[500, 502, 503, 504],
        allowed_methods=["GET", "POST"],
    )
    adapter = HTTPAdapter(max_retries=retry_strategy)
    session.mount("https://", adapter)
    session.mount("http://", adapter)

    return session


def is_rate_limit_error(exception: Exception) -> bool:
    """Check if an exception indicates rate limiting."""
    error_str = str(exception).lower()
    rate_limit_indicators = [
        "429",
        "too many requests",
        "rate limit",
        "rate-limit",
        "throttl",
        "quota exceeded",
    ]
    return any(indicator in error_str for indicator in rate_limit_indicators)


def is_server_error(exception: Exception) -> bool:
    """Check if an exception indicates a server error (5xx)."""
    error_str = str(exception)
    return any(str(code) in error_str for code in [500, 502, 503, 504])


# Global circuit breaker for NBA API
nba_api_circuit_breaker = CircuitBreaker(name="nba_api")

# Global session for NBA API calls
_nba_session: requests.Session | None = None


def get_nba_session() -> requests.Session:
    """Get or create the global NBA API session."""
    global _nba_session
    if _nba_session is None:
        _nba_session = create_nba_session()
    return _nba_session


def reset_nba_session() -> None:
    """Reset the global NBA API session."""
    global _nba_session
    if _nba_session:
        _nba_session.close()
    _nba_session = None
