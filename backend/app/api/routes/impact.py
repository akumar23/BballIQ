from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.season import get_current_season
from app.db.session import get_db
from app.models import ContextualizedImpact, Player, PlayerOnOffStats
from app.schemas.impact import (
    ImpactContext,
    ImpactLeaderboardEntry,
    ImpactRating,
    OnOffStats,
    PlayerImpact,
)

router = APIRouter()


@router.get("/leaderboard", response_model=list[ImpactLeaderboardEntry])
async def get_impact_leaderboard(
    season: str | None = Query(default=None),
    limit: int = Query(default=50, le=100),
    sort_by: str = Query(default="net", pattern="^(net|offense|defense)$"),
    db: Session = Depends(get_db),
):
    """Get players ranked by contextualized impact.

    Args:
        season: NBA season string
        limit: Number of results (max 100)
        sort_by: Sort field - 'net', 'offense', or 'defense'
    """
    season = season or get_current_season()
    # Determine sort column
    sort_column = {
        "net": ContextualizedImpact.contextualized_net_impact,
        "offense": ContextualizedImpact.contextualized_off_impact,
        "defense": ContextualizedImpact.contextualized_def_impact,
    }.get(sort_by, ContextualizedImpact.contextualized_net_impact)

    results = (
        db.query(Player, ContextualizedImpact)
        .join(ContextualizedImpact, Player.id == ContextualizedImpact.player_id)
        .filter(ContextualizedImpact.season == season)
        .filter(ContextualizedImpact.contextualized_net_impact.isnot(None))
        .order_by(desc(sort_column))
        .limit(limit)
        .all()
    )

    return [
        ImpactLeaderboardEntry(
            id=player.id,
            nba_id=player.nba_id,
            name=player.name,
            position=player.position,
            team_abbreviation=player.team_abbreviation,
            contextualized_net_impact=impact.contextualized_net_impact,
            contextualized_off_impact=impact.contextualized_off_impact,
            contextualized_def_impact=impact.contextualized_def_impact,
            raw_net_rating_diff=impact.raw_net_rating_diff,
            teammate_adjustment=impact.teammate_adjustment,
            reliability_factor=impact.reliability_factor,
            impact_percentile=impact.impact_percentile,
        )
        for player, impact in results
    ]


@router.get("/players", response_model=list[PlayerImpact])
async def get_all_player_impacts(
    season: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Get impact data for all players with pagination."""
    season = season or get_current_season()
    results = (
        db.query(Player, PlayerOnOffStats, ContextualizedImpact)
        .outerjoin(PlayerOnOffStats, (Player.id == PlayerOnOffStats.player_id) & (PlayerOnOffStats.season == season))
        .outerjoin(ContextualizedImpact, (Player.id == ContextualizedImpact.player_id) & (ContextualizedImpact.season == season))
        .filter(PlayerOnOffStats.on_court_minutes.isnot(None))
        .order_by(desc(ContextualizedImpact.contextualized_net_impact))
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        _build_player_impact(player, on_off, impact, season)
        for player, on_off, impact in results
    ]


@router.get("/players/{player_id}", response_model=PlayerImpact)
async def get_player_impact(
    player_id: int,
    season: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get detailed impact data for a specific player."""
    season = season or get_current_season()
    result = (
        db.query(Player, PlayerOnOffStats, ContextualizedImpact)
        .outerjoin(PlayerOnOffStats, (Player.id == PlayerOnOffStats.player_id) & (PlayerOnOffStats.season == season))
        .outerjoin(ContextualizedImpact, (Player.id == ContextualizedImpact.player_id) & (ContextualizedImpact.season == season))
        .filter(Player.id == player_id)
        .first()
    )

    if not result:
        raise HTTPException(status_code=404, detail="Player not found")

    player, on_off, impact = result
    return _build_player_impact(player, on_off, impact, season)


def _build_player_impact(
    player: Player,
    on_off: PlayerOnOffStats | None,
    impact: ContextualizedImpact | None,
    season: str,
) -> PlayerImpact:
    """Build PlayerImpact response from database models."""
    on_off_stats = None
    if on_off:
        on_off_stats = OnOffStats(
            on_court_minutes=on_off.on_court_minutes,
            on_court_net_rating=on_off.on_court_net_rating,
            on_court_off_rating=on_off.on_court_off_rating,
            on_court_def_rating=on_off.on_court_def_rating,
            off_court_minutes=on_off.off_court_minutes,
            off_court_net_rating=on_off.off_court_net_rating,
            off_court_off_rating=on_off.off_court_off_rating,
            off_court_def_rating=on_off.off_court_def_rating,
            net_rating_diff=on_off.net_rating_diff,
            off_rating_diff=on_off.off_rating_diff,
            def_rating_diff=on_off.def_rating_diff,
        )

    context = None
    impact_rating = None
    if impact:
        context = ImpactContext(
            avg_teammate_net_rating=impact.avg_teammate_net_rating,
            teammate_adjustment=impact.teammate_adjustment,
            pct_minutes_vs_starters=impact.pct_minutes_vs_starters,
            opponent_quality_factor=impact.opponent_quality_factor,
            reliability_factor=impact.reliability_factor,
        )
        impact_rating = ImpactRating(
            raw_net_rating_diff=impact.raw_net_rating_diff,
            raw_off_rating_diff=impact.raw_off_rating_diff,
            raw_def_rating_diff=impact.raw_def_rating_diff,
            contextualized_net_impact=impact.contextualized_net_impact,
            contextualized_off_impact=impact.contextualized_off_impact,
            contextualized_def_impact=impact.contextualized_def_impact,
            impact_percentile=impact.impact_percentile,
            offensive_impact_percentile=impact.offensive_impact_percentile,
            defensive_impact_percentile=impact.defensive_impact_percentile,
        )

    return PlayerImpact(
        id=player.id,
        nba_id=player.nba_id,
        name=player.name,
        position=player.position,
        team_abbreviation=player.team_abbreviation,
        season=season,
        on_off_stats=on_off_stats,
        context=context,
        impact=impact_rating,
    )
