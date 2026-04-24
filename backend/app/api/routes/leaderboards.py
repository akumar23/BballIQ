from fastapi import APIRouter, Depends, Query
from fastapi_cache.decorator import cache
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.season import get_current_season
from app.db.session import get_db
from app.models import Player, SeasonStats
from app.schemas.leaderboard import SeasonsList
from app.schemas.player import PlayerList, PlayerMetrics, PlayerPerGameStats
from app.services.composite_leaderboard import compute_composite_rankings

router = APIRouter()

# 60s TTL across the board: these are read-only derived views of season
# aggregates that don't change within a single poll interval. Safe to cache
# publicly because none of these endpoints are user-scoped.
_LEADERBOARD_TTL = 60


def _build_player_list(player: Player, stats: SeasonStats) -> PlayerList:
    """Build a PlayerList response from a Player and their SeasonStats."""
    return PlayerList(
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


@router.get("/offensive", response_model=list[PlayerList])
@cache(expire=_LEADERBOARD_TTL)
async def get_offensive_leaderboard(
    season: str | None = Query(default=None),
    limit: int = Query(default=50, le=100),
    db: Session = Depends(get_db),
):
    """Get players ranked by offensive metric."""
    season = season or get_current_season()
    results = (
        db.query(Player, SeasonStats)
        .join(SeasonStats, Player.id == SeasonStats.player_id)
        .filter(SeasonStats.season == season)
        .filter(SeasonStats.offensive_metric.isnot(None))
        .order_by(desc(SeasonStats.offensive_metric))
        .limit(limit)
        .all()
    )

    return [_build_player_list(player, stats) for player, stats in results]


@router.get("/defensive", response_model=list[PlayerList])
@cache(expire=_LEADERBOARD_TTL)
async def get_defensive_leaderboard(
    season: str | None = Query(default=None),
    limit: int = Query(default=50, le=100),
    db: Session = Depends(get_db),
):
    """Get players ranked by defensive metric."""
    season = season or get_current_season()
    results = (
        db.query(Player, SeasonStats)
        .join(SeasonStats, Player.id == SeasonStats.player_id)
        .filter(SeasonStats.season == season)
        .filter(SeasonStats.defensive_metric.isnot(None))
        .order_by(desc(SeasonStats.defensive_metric))
        .limit(limit)
        .all()
    )

    return [_build_player_list(player, stats) for player, stats in results]


@router.get("/per-game", response_model=list[PlayerPerGameStats])
@cache(expire=_LEADERBOARD_TTL)
async def get_per_game_leaderboard(
    season: str | None = Query(default=None),
    limit: int = Query(default=50, le=100),
    sort_by: str = Query(default="ppg"),
    db: Session = Depends(get_db),
):
    """Get players ranked by per-game stats (ppg, rpg, apg, mpg, spg, bpg)."""
    season = season or get_current_season()

    def per_game(total, gp):
        return round(total / gp, 1) if total and gp else None

    results = (
        db.query(Player, SeasonStats)
        .join(SeasonStats, Player.id == SeasonStats.player_id)
        .filter(SeasonStats.season == season)
        .filter(SeasonStats.games_played > 0)
        .all()
    )

    players = [
        PlayerPerGameStats(
            id=player.id,
            nba_id=player.nba_id,
            name=player.name,
            position=player.position,
            team_abbreviation=player.team_abbreviation,
            games_played=stats.games_played,
            ppg=per_game(stats.total_points, stats.games_played),
            rpg=per_game(stats.total_rebounds, stats.games_played),
            apg=per_game(stats.total_assists, stats.games_played),
            mpg=per_game(float(stats.total_minutes) if stats.total_minutes else None, stats.games_played),
            spg=per_game(stats.total_steals, stats.games_played),
            bpg=per_game(stats.total_blocks, stats.games_played),
        )
        for player, stats in results
    ]

    players.sort(key=lambda p: getattr(p, sort_by) or 0, reverse=True)
    return players[:limit]


@router.get("/overall", response_model=list[PlayerList])
@cache(expire=_LEADERBOARD_TTL)
async def get_overall_leaderboard(
    season: str | None = Query(default=None),
    limit: int = Query(default=50, le=100),
    db: Session = Depends(get_db),
):
    """Get players ranked by composite (weighted z-score across 5 categories).

    Categories: scoring, playmaking, rebounding, defense, impact. See
    ``app.services.composite_leaderboard`` for weights and stat definitions.
    """
    season = season or get_current_season()
    ranked = compute_composite_rankings(db, season, limit=limit)
    return [
        PlayerList(
            id=r.player.id,
            nba_id=r.player.nba_id,
            name=r.player.name,
            position=r.player.position,
            team_abbreviation=r.player.team_abbreviation,
            metrics=PlayerMetrics(
                offensive_metric=r.season_stats.offensive_metric,
                defensive_metric=r.season_stats.defensive_metric,
                overall_metric=r.season_stats.overall_metric,
                offensive_percentile=r.season_stats.offensive_percentile,
                defensive_percentile=r.season_stats.defensive_percentile,
                composite_score=round(r.composite_score, 3),
                composite_rank=r.rank,
                category_scores={k: round(v, 3) for k, v in r.category_scores.items()},
            ),
        )
        for r in ranked
    ]

@router.get("/seasons", response_model=list[SeasonsList])
@cache(expire=_LEADERBOARD_TTL)
async def get_leaderboard_seasons(
    db: Session = Depends(get_db)
):

    """Get list of seasons with available leaderboard data."""
    results = (
        db.query(SeasonStats.season)
        .distinct()
        .order_by(desc(SeasonStats.season))
        .all()
        )

    return[
        SeasonsList(
            season=row.season
        )
        for row in results
    ]
