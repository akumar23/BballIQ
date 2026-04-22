"""Pytest configuration and shared fixtures for backend tests.

This module provides two groups of fixtures:

1. **Unit-test helpers** (``mock_settings``, ``fake_redis_client``,
   ``mock_redis_unavailable``, ``sample_*``, ``reset_circuit_breakers``)
   used by low-level service tests that do not touch FastAPI or the DB.

2. **Route-test helpers** (``db_engine``, ``seeded_session``, ``make_client``)
   that spin up an in-memory SQLite database, create the ORM schema, and
   return a FastAPI ``TestClient`` with the DB dependency + ``FastAPICache``
   swapped for in-process equivalents. These are used by every
   ``test_*_routes.py`` file so new route tests can be added without
   duplicating the fixture plumbing.
"""

from __future__ import annotations

from collections.abc import Callable, Iterator
from dataclasses import dataclass
from typing import TYPE_CHECKING
from unittest.mock import MagicMock, patch  # noqa: F401  re-exported for legacy tests

import fakeredis
import pytest

if TYPE_CHECKING:
    from fastapi.testclient import TestClient
    from sqlalchemy.engine import Engine
    from sqlalchemy.orm import Session


# ---------------------------------------------------------------------------
# Legacy unit-test fixtures (kept verbatim so existing tests still pass)
# ---------------------------------------------------------------------------


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
def mock_settings() -> MockSettings:
    """Provide mock settings for tests."""
    return MockSettings()


@pytest.fixture
def fake_redis_client() -> fakeredis.FakeRedis:
    """Provide a fakeredis client for testing."""
    return fakeredis.FakeRedis(decode_responses=True)


@pytest.fixture
def mock_redis_unavailable() -> MagicMock:
    """Provide a mock Redis client that simulates connection failure."""
    mock_client = MagicMock()
    mock_client.ping.side_effect = ConnectionError("Connection refused")
    mock_client.get.side_effect = ConnectionError("Connection refused")
    mock_client.setex.side_effect = ConnectionError("Connection refused")
    return mock_client


@pytest.fixture(autouse=True)
def reset_circuit_breakers() -> Iterator[None]:
    """Reset all circuit breakers before each test."""
    # Import here to avoid circular imports
    from app.services.pbp_data import pbp_stats_circuit_breaker
    from app.services.rate_limiter import nba_api_circuit_breaker

    nba_api_circuit_breaker.reset()
    pbp_stats_circuit_breaker.reset()
    yield
    nba_api_circuit_breaker.reset()
    pbp_stats_circuit_breaker.reset()


@pytest.fixture
def sample_player_data() -> list[dict[str, object]]:
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
def sample_tracking_stats() -> list[dict[str, object]]:
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
def sample_traditional_stats() -> list[dict[str, object]]:
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


# ---------------------------------------------------------------------------
# Route-test fixtures: in-memory SQLite + TestClient + InMemoryBackend cache
# ---------------------------------------------------------------------------
#
# The ``StaticPool`` + ``check_same_thread=False`` dance is required so that
# TestClient's threaded workers all see the same in-memory DB. SQLite does
# not support Postgres extensions like ``pg_trgm`` or ``ON CONFLICT``-style
# dialect-specific inserts, so route-level tests stick to ORM operations
# and the ILIKE fallback paths that the real endpoints provide.


@pytest.fixture()
def db_engine() -> Iterator[Engine]:
    """Yield a fresh SQLite in-memory engine with the ORM schema created.

    The engine is shared across the session factory produced by
    :func:`seeded_session` and the one used by the ``make_client`` fixture,
    so seeded rows are visible to route handlers invoked via
    :class:`fastapi.testclient.TestClient`.
    """
    from sqlalchemy import create_engine
    from sqlalchemy.pool import StaticPool

    from app.models.base import Base

    engine = create_engine(
        "sqlite://",
        connect_args={"check_same_thread": False},
        poolclass=StaticPool,
    )
    Base.metadata.create_all(engine)
    try:
        yield engine
    finally:
        Base.metadata.drop_all(engine)
        engine.dispose()


SeederFn = Callable[["Session"], None]


@pytest.fixture()
def seeded_session(db_engine: Engine) -> Callable[[SeederFn | None], Session]:
    """Return a factory that runs a seeding callable against ``db_engine``.

    The factory returns an open SQLAlchemy ``Session`` bound to the same
    engine as the TestClient so the test can also query / mutate directly
    if needed. Tests must close the returned session themselves (or let
    the teardown of ``db_engine`` handle it).

    Usage::

        def test_something(seeded_session, make_client):
            session = seeded_session(lambda db: _seed_rows(db))
            client = make_client()
            ...
    """
    from sqlalchemy.orm import sessionmaker

    testing_session_local = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine
    )

    def _factory(seeder: SeederFn | None = None) -> Session:
        session = testing_session_local()
        if seeder is not None:
            seeder(session)
            session.commit()
        return session

    return _factory


@pytest.fixture()
def make_client(db_engine: Engine) -> Iterator[Callable[[], TestClient]]:
    """Return a factory that produces a configured ``TestClient``.

    The factory (rather than a direct ``TestClient`` fixture) lets each test
    seed the database *before* the client is created, which matches the
    ordering in ``test_players_routes.py``'s original design.

    The factory:

    1. Overrides ``get_db`` to yield sessions bound to ``db_engine``.
    2. Installs an ``InMemoryBackend`` for ``FastAPICache`` so ``@cache``
       decorators become deterministic in-process no-ops.
    3. Yields a ``TestClient`` context-managed so the app lifespan runs
       (which safely no-ops the duplicate ``FastAPICache.init`` call).
    """
    from fastapi.testclient import TestClient as _TestClient
    from fastapi_cache import FastAPICache
    from fastapi_cache.backends.inmemory import InMemoryBackend
    from sqlalchemy.orm import Session as _Session
    from sqlalchemy.orm import sessionmaker

    from app.core.cache import request_key_builder
    from app.db.session import get_db
    from app.main import app

    testing_session_local = sessionmaker(
        autocommit=False, autoflush=False, bind=db_engine
    )

    def _override_get_db() -> Iterator[_Session]:
        session = testing_session_local()
        try:
            yield session
        finally:
            session.close()

    app.dependency_overrides[get_db] = _override_get_db

    FastAPICache.reset()
    FastAPICache.init(
        InMemoryBackend(),
        prefix="test-cache",
        key_builder=request_key_builder,
    )

    clients: list[_TestClient] = []

    def _factory() -> _TestClient:
        # ``TestClient(app)`` as a context manager drives the lifespan, which
        # tries to init fastapi-cache against a real Redis. Our ``init`` above
        # already flipped the class-level flag, so the lifespan's ``init``
        # call is a no-op.
        tc = _TestClient(app, raise_server_exceptions=True)
        tc.__enter__()
        clients.append(tc)
        return tc

    try:
        yield _factory
    finally:
        for tc in clients:
            try:
                tc.__exit__(None, None, None)
            except Exception:  # noqa: BLE001 - teardown is best-effort
                pass
        app.dependency_overrides.clear()
        FastAPICache.reset()
