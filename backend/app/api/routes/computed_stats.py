"""API routes for computed advanced stats, career trajectory, and shooting tracking."""

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.core.season import get_current_season
from app.db.session import get_db
from app.models import Player
from app.models.career_stats import PlayerCareerStats as PlayerCareerStatsModel
from app.models.computed_advanced import PlayerComputedAdvanced
from app.models.shooting_tracking import PlayerShootingTracking
from app.schemas.computed_stats import (
    CareerSeason,
    ComputedAdvancedStats,
    PlayerCareerResponse,
    PlayerComputedStatsResponse,
    PlayerShootingTrackingResponse,
    RadarData,
    ShootingTrackingStats,
)

router = APIRouter()


def _build_computed_stats_response(
    player: Player,
    computed: PlayerComputedAdvanced | None,
    season: str,
) -> PlayerComputedStatsResponse:
    """Build PlayerComputedStatsResponse from database models."""
    computed_stats = None
    radar = None

    if computed:
        computed_stats = ComputedAdvancedStats(
            per=computed.per,
            obpm=computed.obpm,
            dbpm=computed.dbpm,
            bpm=computed.bpm,
            vorp=computed.vorp,
            ows=computed.ows,
            dws=computed.dws,
            ws=computed.ws,
            ws_per_48=computed.ws_per_48,
        )
        radar = RadarData(
            scoring=computed.radar_scoring,
            playmaking=computed.radar_playmaking,
            defense=computed.radar_defense,
            efficiency=computed.radar_efficiency,
            volume=computed.radar_volume,
            durability=computed.radar_durability,
            clutch=computed.radar_clutch,
            versatility=computed.radar_versatility,
        )

    return PlayerComputedStatsResponse(
        id=player.id,
        nba_id=player.nba_id,
        name=player.name,
        position=player.position,
        team_abbreviation=player.team_abbreviation,
        season=season,
        computed=computed_stats,
        radar=radar,
    )


def _build_shooting_response(
    player: Player,
    shooting: PlayerShootingTracking | None,
    season: str,
) -> PlayerShootingTrackingResponse:
    """Build PlayerShootingTrackingResponse from database models."""
    shooting_stats = None

    if shooting:
        shooting_stats = ShootingTrackingStats(
            catch_shoot_fgm=shooting.catch_shoot_fgm,
            catch_shoot_fga=shooting.catch_shoot_fga,
            catch_shoot_fg_pct=shooting.catch_shoot_fg_pct,
            catch_shoot_fg3_pct=shooting.catch_shoot_fg3_pct,
            catch_shoot_pts=shooting.catch_shoot_pts,
            catch_shoot_efg_pct=shooting.catch_shoot_efg_pct,
            pullup_fgm=shooting.pullup_fgm,
            pullup_fga=shooting.pullup_fga,
            pullup_fg_pct=shooting.pullup_fg_pct,
            pullup_fg3_pct=shooting.pullup_fg3_pct,
            pullup_pts=shooting.pullup_pts,
            pullup_efg_pct=shooting.pullup_efg_pct,
            drives=shooting.drives,
            drive_fgm=shooting.drive_fgm,
            drive_fga=shooting.drive_fga,
            drive_fg_pct=shooting.drive_fg_pct,
            drive_pts=shooting.drive_pts,
            drive_ast=shooting.drive_ast,
            drive_tov=shooting.drive_tov,
        )

    return PlayerShootingTrackingResponse(
        id=player.id,
        nba_id=player.nba_id,
        name=player.name,
        position=player.position,
        team_abbreviation=player.team_abbreviation,
        season=season,
        shooting=shooting_stats,
    )


@router.get("/computed", response_model=list[PlayerComputedStatsResponse])
async def get_computed_stats(
    season: str | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Get computed advanced stats for all players with pagination.

    Includes PER, BPM, VORP, Win Shares, and radar percentiles.
    Sorted by PER descending by default.

    Args:
        season: NBA season string
        limit: Number of results (max 500)
        offset: Number of results to skip
    """
    season = season or get_current_season()
    results = (
        db.query(Player, PlayerComputedAdvanced)
        .outerjoin(
            PlayerComputedAdvanced,
            (Player.id == PlayerComputedAdvanced.player_id)
            & (PlayerComputedAdvanced.season == season),
        )
        .filter(PlayerComputedAdvanced.per.isnot(None))
        .order_by(desc(PlayerComputedAdvanced.per))
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        _build_computed_stats_response(player, computed, season)
        for player, computed in results
    ]


@router.get("/computed/{player_id}", response_model=PlayerComputedStatsResponse)
async def get_player_computed_stats(
    player_id: int,
    season: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get computed advanced stats for a single player.

    Args:
        player_id: Internal player ID
        season: NBA season string
    """
    season = season or get_current_season()
    result = (
        db.query(Player, PlayerComputedAdvanced)
        .outerjoin(
            PlayerComputedAdvanced,
            (Player.id == PlayerComputedAdvanced.player_id)
            & (PlayerComputedAdvanced.season == season),
        )
        .filter(Player.id == player_id)
        .first()
    )

    if not result:
        raise HTTPException(status_code=404, detail="Player not found")

    player, computed = result
    return _build_computed_stats_response(player, computed, season)


@router.get("/career/{player_id}", response_model=PlayerCareerResponse)
async def get_player_career(
    player_id: int,
    db: Session = Depends(get_db),
):
    """Get career trajectory for a player.

    Returns all historical seasons ordered chronologically.

    Args:
        player_id: Internal player ID
    """
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    career_rows = (
        db.query(PlayerCareerStatsModel)
        .filter(PlayerCareerStatsModel.player_id == player_id)
        .order_by(PlayerCareerStatsModel.season)
        .all()
    )

    seasons = [
        CareerSeason(
            season=row.season,
            team_abbreviation=row.team_abbreviation,
            games_played=row.games_played,
            minutes=row.minutes,
            ppg=row.ppg,
            rpg=row.rpg,
            apg=row.apg,
            spg=row.spg,
            bpg=row.bpg,
            fg_pct=row.fg_pct,
            fg3_pct=row.fg3_pct,
            ft_pct=row.ft_pct,
        )
        for row in career_rows
    ]

    return PlayerCareerResponse(
        id=player.id,
        nba_id=player.nba_id,
        name=player.name,
        position=player.position,
        team_abbreviation=player.team_abbreviation,
        seasons=seasons,
    )


@router.get("/shooting", response_model=list[PlayerShootingTrackingResponse])
async def get_shooting_tracking(
    season: str | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Get shooting tracking stats for all players with pagination.

    Args:
        season: NBA season string
        limit: Number of results (max 500)
        offset: Number of results to skip
    """
    season = season or get_current_season()
    results = (
        db.query(Player, PlayerShootingTracking)
        .outerjoin(
            PlayerShootingTracking,
            (Player.id == PlayerShootingTracking.player_id)
            & (PlayerShootingTracking.season == season),
        )
        .filter(PlayerShootingTracking.catch_shoot_fga.isnot(None))
        .order_by(desc(PlayerShootingTracking.catch_shoot_pts))
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        _build_shooting_response(player, shooting, season)
        for player, shooting in results
    ]


@router.get("/shooting/{player_id}", response_model=PlayerShootingTrackingResponse)
async def get_player_shooting_tracking(
    player_id: int,
    season: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get shooting tracking stats for a single player.

    Args:
        player_id: Internal player ID
        season: NBA season string
    """
    season = season or get_current_season()
    result = (
        db.query(Player, PlayerShootingTracking)
        .outerjoin(
            PlayerShootingTracking,
            (Player.id == PlayerShootingTracking.player_id)
            & (PlayerShootingTracking.season == season),
        )
        .filter(Player.id == player_id)
        .first()
    )

    if not result:
        raise HTTPException(status_code=404, detail="Player not found")

    player, shooting = result
    return _build_shooting_response(player, shooting, season)
