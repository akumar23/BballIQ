"""Unit tests for the rate limiter module.

This module tests:
- CircuitBreaker state transitions (CLOSED -> OPEN -> HALF_OPEN -> CLOSED)
- Circuit breaker failure threshold behavior
- Circuit recovery after timeout
- Exponential backoff delay calculation
- Jitter range validation
- Rate limit and server error detection
"""

import time
from unittest.mock import patch

import pytest

from app.services.rate_limiter import (
    CircuitBreaker,
    CircuitState,
    calculate_backoff_delay,
    is_rate_limit_error,
    is_server_error,
)


class TestCircuitBreaker:
    """Tests for CircuitBreaker state machine."""

    def test_initial_state_is_closed(self, mock_settings):
        """Verify circuit breaker starts in CLOSED state."""
        with patch("app.services.rate_limiter.settings", mock_settings):
            breaker = CircuitBreaker(name="test")
            assert breaker.state == CircuitState.CLOSED

    def test_can_execute_when_closed(self, mock_settings):
        """Verify requests are allowed when circuit is closed."""
        with patch("app.services.rate_limiter.settings", mock_settings):
            breaker = CircuitBreaker(name="test")
            assert breaker.can_execute() is True

    def test_opens_after_failure_threshold(self, mock_settings):
        """Verify circuit opens after reaching failure threshold."""
        with patch("app.services.rate_limiter.settings", mock_settings):
            breaker = CircuitBreaker(name="test", failure_threshold=3)

            # Record failures up to threshold
            for _ in range(3):
                breaker.record_failure()

            assert breaker.state == CircuitState.OPEN
            assert breaker.can_execute() is False

    def test_does_not_open_before_threshold(self, mock_settings):
        """Verify circuit stays closed before reaching threshold."""
        with patch("app.services.rate_limiter.settings", mock_settings):
            breaker = CircuitBreaker(name="test", failure_threshold=5)

            # Record failures below threshold
            for _ in range(4):
                breaker.record_failure()

            assert breaker.state == CircuitState.CLOSED
            assert breaker.can_execute() is True

    def test_success_resets_failure_count_when_closed(self, mock_settings):
        """Verify successful call resets failure count in closed state."""
        with patch("app.services.rate_limiter.settings", mock_settings):
            breaker = CircuitBreaker(name="test", failure_threshold=5)

            # Record some failures
            breaker.record_failure()
            breaker.record_failure()

            # Record success
            breaker.record_success()

            # Failure count should be reset, so we need full threshold again
            for _ in range(4):
                breaker.record_failure()

            # Should still be closed (only 4 failures since reset)
            assert breaker.state == CircuitState.CLOSED

    def test_transitions_to_half_open_after_timeout(self, mock_settings):
        """Verify circuit transitions to HALF_OPEN after recovery timeout."""
        with patch("app.services.rate_limiter.settings", mock_settings):
            breaker = CircuitBreaker(
                name="test",
                failure_threshold=2,
                recovery_timeout=0.1,  # 100ms for fast test
            )

            # Open the circuit
            breaker.record_failure()
            breaker.record_failure()
            assert breaker.state == CircuitState.OPEN

            # Wait for recovery timeout
            time.sleep(0.15)

            # Check state - should transition to HALF_OPEN
            assert breaker.state == CircuitState.HALF_OPEN

    def test_half_open_allows_limited_calls(self, mock_settings):
        """Verify HALF_OPEN state allows limited number of test calls."""
        with patch("app.services.rate_limiter.settings", mock_settings):
            breaker = CircuitBreaker(
                name="test",
                failure_threshold=2,
                recovery_timeout=0.05,
                half_open_max_calls=2,
            )

            # Open and wait for half-open
            breaker.record_failure()
            breaker.record_failure()
            time.sleep(0.1)

            # Trigger transition to HALF_OPEN
            assert breaker.state == CircuitState.HALF_OPEN

            # Should allow limited calls
            assert breaker.can_execute() is True
            assert breaker.can_execute() is True
            # After max calls, should reject
            assert breaker.can_execute() is False

    def test_half_open_closes_on_success(self, mock_settings):
        """Verify circuit closes after enough successes in HALF_OPEN."""
        with patch("app.services.rate_limiter.settings", mock_settings):
            breaker = CircuitBreaker(
                name="test",
                failure_threshold=2,
                recovery_timeout=0.05,
                half_open_max_calls=2,
            )

            # Open and transition to half-open
            breaker.record_failure()
            breaker.record_failure()
            time.sleep(0.1)
            _ = breaker.state  # Trigger transition

            # Record enough successes
            breaker.can_execute()  # First call
            breaker.record_success()
            breaker.can_execute()  # Second call
            breaker.record_success()

            assert breaker.state == CircuitState.CLOSED

    def test_half_open_reopens_on_failure(self, mock_settings):
        """Verify circuit reopens on any failure during HALF_OPEN."""
        with patch("app.services.rate_limiter.settings", mock_settings):
            breaker = CircuitBreaker(
                name="test",
                failure_threshold=2,
                recovery_timeout=0.05,
                half_open_max_calls=3,
            )

            # Open and transition to half-open
            breaker.record_failure()
            breaker.record_failure()
            time.sleep(0.1)
            _ = breaker.state  # Trigger transition to HALF_OPEN

            assert breaker.state == CircuitState.HALF_OPEN

            # Record a failure
            breaker.record_failure()

            assert breaker.state == CircuitState.OPEN

    def test_reset_returns_to_closed(self, mock_settings):
        """Verify manual reset returns circuit to CLOSED state."""
        with patch("app.services.rate_limiter.settings", mock_settings):
            breaker = CircuitBreaker(name="test", failure_threshold=2)

            # Open the circuit
            breaker.record_failure()
            breaker.record_failure()
            assert breaker.state == CircuitState.OPEN

            # Reset
            breaker.reset()

            assert breaker.state == CircuitState.CLOSED
            assert breaker.can_execute() is True


class TestCalculateBackoffDelay:
    """Tests for exponential backoff delay calculation."""

    def test_first_attempt_uses_base_delay(self):
        """Verify first attempt (attempt=0) uses base delay."""
        delay = calculate_backoff_delay(
            attempt=0,
            base_delay=1.0,
            backoff_base=2.0,
            max_delay=100.0,
            jitter_max=0.0,  # No jitter for predictable test
        )
        assert delay == 1.0

    def test_exponential_increase(self):
        """Verify delay increases exponentially with attempts."""
        delays = []
        for attempt in range(4):
            delay = calculate_backoff_delay(
                attempt=attempt,
                base_delay=1.0,
                backoff_base=2.0,
                max_delay=100.0,
                jitter_max=0.0,
            )
            delays.append(delay)

        # Expected: 1, 2, 4, 8
        assert delays == [1.0, 2.0, 4.0, 8.0]

    def test_respects_max_delay_cap(self):
        """Verify delay is capped at max_delay."""
        delay = calculate_backoff_delay(
            attempt=10,  # Would be 1024 without cap
            base_delay=1.0,
            backoff_base=2.0,
            max_delay=50.0,
            jitter_max=0.0,
        )
        assert delay == 50.0

    def test_jitter_is_within_range(self):
        """Verify jitter adds randomness within expected range."""
        base_delay = 1.0
        jitter_max = 0.5

        # Run multiple times to test randomness
        for _ in range(100):
            delay = calculate_backoff_delay(
                attempt=0,
                base_delay=base_delay,
                backoff_base=2.0,
                max_delay=100.0,
                jitter_max=jitter_max,
            )
            # Delay should be between base and base + (base * jitter_max)
            assert delay >= base_delay
            assert delay <= base_delay * (1 + jitter_max)

    def test_jitter_adds_variability(self):
        """Verify jitter produces different values across calls."""
        delays = set()
        for _ in range(20):
            delay = calculate_backoff_delay(
                attempt=0,
                base_delay=1.0,
                backoff_base=2.0,
                max_delay=100.0,
                jitter_max=0.5,
            )
            delays.add(round(delay, 3))

        # With jitter, we should see multiple different values
        assert len(delays) > 1

    def test_uses_settings_defaults(self, mock_settings):
        """Verify function uses settings when parameters not provided."""
        with patch("app.services.rate_limiter.settings", mock_settings):
            delay = calculate_backoff_delay(attempt=0, jitter_max=0.0)
            assert delay == mock_settings.nba_api_base_delay


class TestIsRateLimitError:
    """Tests for rate limit error detection."""

    @pytest.mark.parametrize(
        "error_message",
        [
            "429 Too Many Requests",
            "HTTP 429",
            "rate limit exceeded",
            "Rate-Limit reached",
            "too many requests",
            "throttling error",
            "quota exceeded for API",
        ],
    )
    def test_detects_rate_limit_errors(self, error_message):
        """Verify various rate limit error messages are detected."""
        exception = Exception(error_message)
        assert is_rate_limit_error(exception) is True

    @pytest.mark.parametrize(
        "error_message",
        [
            "Connection timeout",
            "Server error",
            "Invalid response",
            "Authentication failed",
        ],
    )
    def test_does_not_match_non_rate_limit_errors(self, error_message):
        """Verify non-rate-limit errors are not flagged."""
        exception = Exception(error_message)
        assert is_rate_limit_error(exception) is False


class TestIsServerError:
    """Tests for server error detection."""

    @pytest.mark.parametrize("status_code", [500, 502, 503, 504])
    def test_detects_server_error_codes(self, status_code):
        """Verify 5xx status codes are detected."""
        exception = Exception(f"HTTP {status_code} Server Error")
        assert is_server_error(exception) is True

    @pytest.mark.parametrize("status_code", [400, 401, 403, 404, 429])
    def test_does_not_match_client_errors(self, status_code):
        """Verify 4xx status codes are not flagged as server errors."""
        exception = Exception(f"HTTP {status_code} Client Error")
        assert is_server_error(exception) is False


class TestCircuitBreakerThreadSafety:
    """Tests for circuit breaker thread safety."""

    def test_concurrent_access_to_state(self, mock_settings):
        """Verify circuit breaker handles concurrent state access safely."""
        import threading

        with patch("app.services.rate_limiter.settings", mock_settings):
            breaker = CircuitBreaker(
                name="test",
                failure_threshold=100,
            )

            errors = []

            def record_operations():
                try:
                    for _ in range(50):
                        breaker.record_failure()
                        breaker.record_success()
                        _ = breaker.state
                        breaker.can_execute()
                except Exception as e:
                    errors.append(e)

            threads = [threading.Thread(target=record_operations) for _ in range(5)]

            for t in threads:
                t.start()
            for t in threads:
                t.join()

            assert len(errors) == 0
