from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routes import impact, leaderboards, play_types, players
from app.core.config import settings

app = FastAPI(
    title="NBA Advanced Stats API",
    description="Per-touch offensive and defensive metrics for NBA players",
    version="0.1.0",
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


@app.get("/health")
async def health_check():
    return {"status": "healthy"}
