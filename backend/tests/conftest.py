"""Pytest configuration and shared fixtures for unit tests.

This module provides:
- Mock Redis client using fakeredis
- Mock settings configuration
- Shared test fixtures for rate limiter and cache tests
"""

import pytest
from unittest.mock import MagicMock, patch
from dataclasses import dataclass

import fakeredis


@dataclass
class MockSettings:
    """Mock settings for testing."""

    # Redis Cache TTL Configuration
    cache_ttl_default: int = 3600
    cache_ttl_players: int = 3600
    cache_ttl_tracking_stats: int = 3600
    cache_ttl_game_possessions: int = 86400
    cache_enabled: bool = True
    redis_url: str = "redis://localhost:6379/0"

    # Rate Limiting Configuration
    nba_api_base_delay: float = 0.1  # Short delay for tests
    nba_api_max_retries: int = 3
    nba_api_backoff_base: float = 2.0
    nba_api_backoff_max: float = 10.0
    nba_api_jitter_max: float = 0.5
    nba_api_timeout: int = 5
    nba_api_cache_dir: str = "./test_cache"

    # Circuit Breaker Configuration
    circuit_breaker_failure_threshold: int = 3
    circuit_breaker_recovery_timeout: float = 1.0  # Short timeout for tests
    circuit_breaker_half_open_max_calls: int = 2


@pytest.fixture
def mock_settings():
    """Provide mock settings for tests."""
    return MockSettings()


@pytest.fixture
def fake_redis_client():
    """Provide a fakeredis client for testing."""
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def mock_redis_unavailable():
    """Provide a mock Redis client that simulates connection failure."""
    mock_client = MagicMock()
    mock_client.ping.side_effect = ConnectionError("Connection refused")
    mock_client.get.side_effect = ConnectionError("Connection refused")
    mock_client.setex.side_effect = ConnectionError("Connection refused")
    return mock_client


@pytest.fixture(autouse=True)
def reset_circuit_breakers():
    """Reset all circuit breakers before each test."""
    # Import here to avoid circular imports
    from app.services.rate_limiter import nba_api_circuit_breaker
    from app.services.pbp_data import pbp_stats_circuit_breaker

    nba_api_circuit_breaker.reset()
    pbp_stats_circuit_breaker.reset()
    yield
    # Reset again after test
    nba_api_circuit_breaker.reset()
    pbp_stats_circuit_breaker.reset()


@pytest.fixture
def sample_player_data():
    """Provide sample player data for tests."""
    return [
        {
            "PERSON_ID": 1,
            "DISPLAY_FIRST_LAST": "Test Player 1",
            "TEAM_ABBREVIATION": "TST",
        },
        {
            "PERSON_ID": 2,
            "DISPLAY_FIRST_LAST": "Test Player 2",
            "TEAM_ABBREVIATION": "TST",
        },
    ]


@pytest.fixture
def sample_tracking_stats():
    """Provide sample tracking stats for tests."""
    return [
        {
            "PLAYER_ID": 1,
            "PLAYER_NAME": "Test Player 1",
            "TEAM_ABBREVIATION": "TST",
            "TOUCHES": 100,
            "FRONT_CT_TOUCHES": 80,
            "TIME_OF_POSS": 5.5,
            "AVG_SEC_PER_TOUCH": 2.1,
            "AVG_DRIB_PER_TOUCH": 1.5,
            "PTS_PER_TOUCH": 0.4,
        },
    ]


@pytest.fixture
def sample_traditional_stats():
    """Provide sample traditional stats for tests."""
    return [
        {
            "PLAYER_ID": 1,
            "PLAYER_NAME": "Test Player 1",
            "TEAM_ABBREVIATION": "TST",
            "PTS": 500,
            "AST": 100,
            "TOV": 50,
            "FTA": 75,
            "MIN": 1000.0,
        },
    ]
