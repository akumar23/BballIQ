"""FastAPI application entrypoint.

The ``lifespan`` context initialises fastapi-cache2 against the same Redis
instance used by the existing ``redis_cache`` service. fastapi-cache2 uses
``redis.asyncio`` (for the decorator's async hot path), which coexists fine
with the sync ``redis`` client the rest of the app uses.
"""

from __future__ import annotations

import logging
from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi_cache import FastAPICache
from fastapi_cache.backends.redis import RedisBackend
from redis import asyncio as aioredis

from app.api.routes import advanced_stats, computed_stats, impact, leaderboards, play_types, players
from app.core.cache import request_key_builder
from app.core.config import settings

logger = logging.getLogger(__name__)


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
        logger.info("fastapi-cache2 initialised against %s", settings.redis_url)
    except Exception:  # noqa: BLE001 - cache is non-critical
        logger.exception(
            "Failed to initialise fastapi-cache2; endpoints will fall through to DB"
        )
    try:
        yield
    finally:
        FastAPICache.reset()
        try:
            await redis_client.close()
        except Exception:  # noqa: BLE001
            logger.exception("Error closing async Redis client")


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

app.include_router(players.router, prefix="/api/players", tags=["players"])
app.include_router(leaderboards.router, prefix="/api/leaderboards", tags=["leaderboards"])
app.include_router(impact.router, prefix="/api/impact", tags=["impact"])
app.include_router(play_types.router, prefix="/api/play-types", tags=["play-types"])
app.include_router(advanced_stats.router, prefix="/api/stats", tags=["advanced-stats"])
app.include_router(computed_stats.router, prefix="/api/stats", tags=["computed-stats"])


@app.get("/health")
async def health_check() -> dict[str, str]:
    return {"status": "healthy"}
