from fastapi import APIRouter, Depends, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Player, SeasonStats
from app.schemas.player import PlayerList

router = APIRouter()


@router.get("/offensive", response_model=list[PlayerList])
async def get_offensive_leaderboard(
    season: str = Query(default="2024-25"),
    limit: int = Query(default=50, le=100),
    db: Session = Depends(get_db),
):
    """Get players ranked by offensive metric."""
    results = (
        db.query(Player, SeasonStats)
        .join(SeasonStats, Player.id == SeasonStats.player_id)
        .filter(SeasonStats.season == season)
        .filter(SeasonStats.offensive_metric.isnot(None))
        .order_by(desc(SeasonStats.offensive_metric))
        .limit(limit)
        .all()
    )

    return [
        PlayerList(
            id=player.id,
            nba_id=player.nba_id,
            name=player.name,
            position=player.position,
            team_abbreviation=player.team_abbreviation,
            metrics={
                "offensive_metric": stats.offensive_metric,
                "defensive_metric": stats.defensive_metric,
                "overall_metric": stats.overall_metric,
                "offensive_percentile": stats.offensive_percentile,
                "defensive_percentile": stats.defensive_percentile,
            },
        )
        for player, stats in results
    ]


@router.get("/defensive", response_model=list[PlayerList])
async def get_defensive_leaderboard(
    season: str = Query(default="2024-25"),
    limit: int = Query(default=50, le=100),
    db: Session = Depends(get_db),
):
    """Get players ranked by defensive metric."""
    results = (
        db.query(Player, SeasonStats)
        .join(SeasonStats, Player.id == SeasonStats.player_id)
        .filter(SeasonStats.season == season)
        .filter(SeasonStats.defensive_metric.isnot(None))
        .order_by(desc(SeasonStats.defensive_metric))
        .limit(limit)
        .all()
    )

    return [
        PlayerList(
            id=player.id,
            nba_id=player.nba_id,
            name=player.name,
            position=player.position,
            team_abbreviation=player.team_abbreviation,
            metrics={
                "offensive_metric": stats.offensive_metric,
                "defensive_metric": stats.defensive_metric,
                "overall_metric": stats.overall_metric,
                "offensive_percentile": stats.offensive_percentile,
                "defensive_percentile": stats.defensive_percentile,
            },
        )
        for player, stats in results
    ]


@router.get("/overall", response_model=list[PlayerList])
async def get_overall_leaderboard(
    season: str = Query(default="2024-25"),
    limit: int = Query(default=50, le=100),
    db: Session = Depends(get_db),
):
    """Get players ranked by overall (combined) metric."""
    results = (
        db.query(Player, SeasonStats)
        .join(SeasonStats, Player.id == SeasonStats.player_id)
        .filter(SeasonStats.season == season)
        .filter(SeasonStats.overall_metric.isnot(None))
        .order_by(desc(SeasonStats.overall_metric))
        .limit(limit)
        .all()
    )

    return [
        PlayerList(
            id=player.id,
            nba_id=player.nba_id,
            name=player.name,
            position=player.position,
            team_abbreviation=player.team_abbreviation,
            metrics={
                "offensive_metric": stats.offensive_metric,
                "defensive_metric": stats.defensive_metric,
                "overall_metric": stats.overall_metric,
                "offensive_percentile": stats.offensive_percentile,
                "defensive_percentile": stats.defensive_percentile,
            },
        )
        for player, stats in results
    ]
