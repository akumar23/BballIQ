"""FastAPI application entrypoint.

The ``lifespan`` context initialises fastapi-cache2 against the same Redis
instance used by the existing ``redis_cache`` service. fastapi-cache2 uses
``redis.asyncio`` (for the decorator's async hot path), which coexists fine
with the sync ``redis`` client the rest of the app uses.

Observability is wired here too:

- ``configure_logging()`` is called first so every subsequent import can
  log through structlog / the JSON-formatted root handler.
- ``init_sentry()`` is called before ``FastAPI(...)`` so the FastAPI
  integration can hook the ASGI middleware chain at construction time.
- A ``request_id`` middleware binds a per-request id into structlog's
  contextvars so downstream log lines include it automatically.
- ``prometheus-fastapi-instrumentator`` exposes ``/metrics`` for Prometheus.
"""

from __future__ import annotations

import uuid
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

import structlog
from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from prometheus_fastapi_instrumentator import Instrumentator
from redis import asyncio as aioredis
from starlette.middleware.base import BaseHTTPMiddleware
from starlette.types import ASGIApp

from app.api.routes import advanced_stats, computed_stats, impact, leaderboards, play_types, players
from app.core.cache import request_key_builder
from app.core.config import settings
from app.core.logging import configure_logging
from app.core.observability import init_sentry

# Configure logging and Sentry BEFORE constructing the FastAPI app so the
# FastApiIntegration picks up the ASGI lifecycle at construction and every
# import below emits through the JSON-formatted root handler.
configure_logging()
init_sentry()

logger = structlog.get_logger(__name__)


@asynccontextmanager
async def lifespan(_app: FastAPI) -> AsyncIterator[None]:
    """Initialise and tear down shared resources (fastapi-cache2)."""
    redis_client = aioredis.from_url(
        settings.redis_url,
        encoding="utf-8",
        decode_responses=False,  # RedisBackend stores raw bytes
    )
    try:
        FastAPICache.init(
            RedisBackend(redis_client),
            prefix="api-cache",
            key_builder=request_key_builder,
        )
        logger.info("fastapi_cache_initialised", redis_url=settings.redis_url)
    except Exception:  # noqa: BLE001 - cache is non-critical
        logger.exception(
            "fastapi_cache_init_failed",
        )
    try:
        yield
    finally:
        FastAPICache.reset()
        try:
            await redis_client.close()
        except Exception:  # noqa: BLE001
            logger.exception("async_redis_close_failed")


class RequestContextMiddleware(BaseHTTPMiddleware):
    """Bind a per-request id into structlog's contextvars for every log line.

    The request id is taken from the ``X-Request-ID`` header if the caller
    supplies one (useful for cross-service tracing) and otherwise generated
    fresh. It is also echoed back in the response so clients can quote it
    when filing bug reports.
    """

    def __init__(self, app: ASGIApp) -> None:
        super().__init__(app)

    async def dispatch(self, request: Request, call_next):
        request_id = request.headers.get("X-Request-ID") or uuid.uuid4().hex
        # bind_contextvars is per-task (via contextvars), so parallel
        # requests see only their own id.
        structlog.contextvars.bind_contextvars(
            request_id=request_id,
            method=request.method,
            path=request.url.path,
        )
        try:
            response = await call_next(request)
        finally:
            structlog.contextvars.clear_contextvars()
        response.headers["X-Request-ID"] = request_id
        return response


app = FastAPI(
    title="StatFloor API",
    description="Per-touch offensive and defensive metrics for NBA players",
    version="0.1.0",
    lifespan=lifespan,
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.cors_origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)
app.add_middleware(RequestContextMiddleware)

# Prometheus metrics on /metrics (same port; no extra container needed).
# Grouping 2xx/3xx/4xx/5xx keeps cardinality sane, and excluding /health and
# /metrics themselves avoids a recursive / noise-y metric about the scrape.
Instrumentator(
    should_group_status_codes=True,
    should_ignore_untemplated=True,
    excluded_handlers=["/health", "/metrics"],
).instrument(app).expose(app, endpoint="/metrics", include_in_schema=False)

app.include_router(players.router, prefix="/api/players", tags=["players"])
app.include_router(leaderboards.router, prefix="/api/leaderboards", tags=["leaderboards"])
app.include_router(impact.router, prefix="/api/impact", tags=["impact"])
app.include_router(play_types.router, prefix="/api/play-types", tags=["play-types"])
app.include_router(advanced_stats.router, prefix="/api/stats", tags=["advanced-stats"])
app.include_router(computed_stats.router, prefix="/api/stats", tags=["computed-stats"])


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}
