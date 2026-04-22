"""API routes for play type statistics."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.season import get_current_season
from app.db.session import get_db
from app.models import Player, SeasonPlayTypeStats
from app.schemas.play_type import (
    PlayTypeLeaderboardEntry,
    PlayTypeLeaderboardResponse,
    PlayTypeMetrics,
    PlayerPlayTypeStats,
    SpotUpMetrics,
)

router = APIRouter()

# Valid play types for querying
PlayType = Literal[
    "isolation",
    "pnr_ball_handler",
    "pnr_roll_man",
    "post_up",
    "spot_up",
    "transition",
    "cut",
    "off_screen",
]

# Minimum possessions for leaderboard eligibility
MIN_POSS_DEFAULT = 50

# Play type display names
PLAY_TYPE_NAMES = {
    "isolation": "Isolation",
    "pnr_ball_handler": "Pick & Roll Ball Handler",
    "pnr_roll_man": "Pick & Roll Roll Man",
    "post_up": "Post-Up",
    "spot_up": "Spot-Up",
    "transition": "Transition",
    "cut": "Cut",
    "off_screen": "Off Screen",
}


def _build_play_type_metrics(stats: SeasonPlayTypeStats, play_type: str) -> PlayTypeMetrics | SpotUpMetrics | None:
    """Build PlayTypeMetrics from SeasonPlayTypeStats for a specific play type."""
    poss = getattr(stats, f"{play_type}_poss", None)
    pts = getattr(stats, f"{play_type}_pts", None)
    ppp = getattr(stats, f"{play_type}_ppp", None)
    fg_pct = getattr(stats, f"{play_type}_fg_pct", None)
    freq = getattr(stats, f"{play_type}_freq", None)
    percentile = getattr(stats, f"{play_type}_ppp_percentile", None)

    if poss is None and pts is None:
        return None

    if play_type == "spot_up":
        return SpotUpMetrics(
            possessions=poss,
            points=pts,
            ppp=ppp,
            fg_pct=fg_pct,
            frequency=freq,
            ppp_percentile=percentile,
            fg3m=stats.spot_up_fg3m,
            fg3a=stats.spot_up_fg3a,
            fg3_pct=stats.spot_up_fg3_pct,
        )

    return PlayTypeMetrics(
        possessions=poss,
        points=pts,
        ppp=ppp,
        fg_pct=fg_pct,
        frequency=freq,
        ppp_percentile=percentile,
    )


@router.get("/leaderboard", response_model=PlayTypeLeaderboardResponse)
async def get_play_type_leaderboard(
    play_type: PlayType = Query(default="isolation", description="Play type to rank by"),
    sort_by: Literal["ppp", "possessions", "fg_pct", "frequency"] = Query(
        default="ppp", description="Stat to sort by"
    ),
    season: str | None = Query(default=None),
    limit: int = Query(default=50, le=100),
    min_poss: int = Query(default=MIN_POSS_DEFAULT, description="Minimum possessions required"),
    db: Session = Depends(get_db),
):
    """Get players ranked by a specific play type stat.

    Args:
        play_type: The play type to rank by (isolation, pnr_ball_handler, etc.)
        sort_by: The stat to sort by (ppp, possessions, fg_pct, frequency)
        season: NBA season string
        limit: Maximum number of results
        min_poss: Minimum possessions required for eligibility
        db: Database session

    Returns:
        PlayTypeLeaderboardResponse with entries sorted by the specified stat
    """
    season = season or get_current_season()
    poss_col = getattr(SeasonPlayTypeStats, f"{play_type}_poss")
    sort_col_name = f"{play_type}_{sort_by}" if sort_by != "possessions" else f"{play_type}_poss"

    # Check if column exists
    if not hasattr(SeasonPlayTypeStats, sort_col_name):
        raise HTTPException(status_code=400, detail=f"Invalid sort column: {sort_col_name}")

    sort_col = getattr(SeasonPlayTypeStats, sort_col_name)

    results = (
        db.query(Player, SeasonPlayTypeStats)
        .join(SeasonPlayTypeStats, Player.id == SeasonPlayTypeStats.player_id)
        .filter(SeasonPlayTypeStats.season == season)
        .filter(poss_col >= min_poss)
        .filter(sort_col.isnot(None))
        .order_by(desc(sort_col))
        .limit(limit)
        .all()
    )

    entries = []
    for rank, (player, stats) in enumerate(results, 1):
        entries.append(
            PlayTypeLeaderboardEntry(
                rank=rank,
                id=player.id,
                nba_id=player.nba_id,
                name=player.name,
                position=player.position,
                team_abbreviation=player.team_abbreviation,
                possessions=getattr(stats, f"{play_type}_poss"),
                points=getattr(stats, f"{play_type}_pts"),
                ppp=getattr(stats, f"{play_type}_ppp"),
                fg_pct=getattr(stats, f"{play_type}_fg_pct"),
                frequency=getattr(stats, f"{play_type}_freq"),
                ppp_percentile=getattr(stats, f"{play_type}_ppp_percentile"),
            )
        )

    return PlayTypeLeaderboardResponse(
        play_type=PLAY_TYPE_NAMES.get(play_type, play_type),
        sort_by=sort_by,
        entries=entries,
    )


@router.get("/players", response_model=list[PlayerPlayTypeStats])
async def get_all_players_play_types(
    season: str | None = Query(default=None),
    limit: int = Query(default=50, le=100),
    offset: int = Query(default=0),
    db: Session = Depends(get_db),
):
    """Get play type stats for all players.

    Args:
        season: NBA season string
        limit: Maximum number of results
        offset: Number of results to skip
        db: Database session

    Returns:
        List of PlayerPlayTypeStats for all players
    """
    season = season or get_current_season()
    results = (
        db.query(Player, SeasonPlayTypeStats)
        .join(SeasonPlayTypeStats, Player.id == SeasonPlayTypeStats.player_id)
        .filter(SeasonPlayTypeStats.season == season)
        .filter(SeasonPlayTypeStats.total_poss > 0)
        .order_by(desc(SeasonPlayTypeStats.total_poss))
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        PlayerPlayTypeStats(
            id=player.id,
            nba_id=player.nba_id,
            name=player.name,
            position=player.position,
            team_abbreviation=player.team_abbreviation,
            season=season,
            total_poss=stats.total_poss,
            isolation=_build_play_type_metrics(stats, "isolation"),
            pnr_ball_handler=_build_play_type_metrics(stats, "pnr_ball_handler"),
            pnr_roll_man=_build_play_type_metrics(stats, "pnr_roll_man"),
            post_up=_build_play_type_metrics(stats, "post_up"),
            spot_up=_build_play_type_metrics(stats, "spot_up"),
            transition=_build_play_type_metrics(stats, "transition"),
            cut=_build_play_type_metrics(stats, "cut"),
            off_screen=_build_play_type_metrics(stats, "off_screen"),
        )
        for player, stats in results
    ]


@router.get("/players/{player_id}", response_model=PlayerPlayTypeStats)
async def get_player_play_types(
    player_id: int,
    season: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get detailed play type stats for a specific player.

    Args:
        player_id: Internal player ID
        season: NBA season string
        db: Database session

    Returns:
        PlayerPlayTypeStats for the specified player

    Raises:
        HTTPException: If player or stats not found
    """
    season = season or get_current_season()
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    stats = (
        db.query(SeasonPlayTypeStats)
        .filter(
            SeasonPlayTypeStats.player_id == player_id,
            SeasonPlayTypeStats.season == season,
        )
        .first()
    )

    if not stats:
        raise HTTPException(
            status_code=404,
            detail=f"Play type stats not found for player {player_id} in season {season}",
        )

    return PlayerPlayTypeStats(
        id=player.id,
        nba_id=player.nba_id,
        name=player.name,
        position=player.position,
        team_abbreviation=player.team_abbreviation,
        season=season,
        total_poss=stats.total_poss,
        isolation=_build_play_type_metrics(stats, "isolation"),
        pnr_ball_handler=_build_play_type_metrics(stats, "pnr_ball_handler"),
        pnr_roll_man=_build_play_type_metrics(stats, "pnr_roll_man"),
        post_up=_build_play_type_metrics(stats, "post_up"),
        spot_up=_build_play_type_metrics(stats, "spot_up"),
        transition=_build_play_type_metrics(stats, "transition"),
        cut=_build_play_type_metrics(stats, "cut"),
        off_screen=_build_play_type_metrics(stats, "off_screen"),
    )
