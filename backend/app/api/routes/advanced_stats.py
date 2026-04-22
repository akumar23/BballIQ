"""API routes for advanced stats, shot zones, clutch stats, and defensive profiles."""

from typing import Literal

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_cache.decorator import cache
from sqlalchemy import asc, desc
from sqlalchemy.orm import Session

from app.core.season import get_current_season
from app.db.session import get_db
from app.models import Player
from app.models.advanced_stats import PlayerAdvancedStats
from app.models.clutch_stats import PlayerClutchStats as PlayerClutchStatsModel
from app.models.defensive_matchups import PlayerDefensiveStats as PlayerDefensiveStatsModel
from app.models.shot_zones import PlayerShotZones as PlayerShotZonesModel
from app.schemas.advanced_stats import (
    AdvancedStats,
    ClutchStats,
    DefenseZoneStats,
    IsoDefenseStats,
    PlayerAdvancedStatsResponse,
    PlayerDefensiveProfile,
    PlayerShotZones,
    ShotZone,
)

router = APIRouter()

# Season-level GETs below use a 60s TTL. Per-player endpoints intentionally
# bypass the cache per product requirements (short TTL doesn't save much on
# single-row reads and the response shapes can be per-player large).
_ADVANCED_STATS_TTL = 60


def _build_advanced_stats_response(
    player: Player,
    advanced: PlayerAdvancedStats | None,
    clutch: PlayerClutchStatsModel | None,
    season: str,
) -> PlayerAdvancedStatsResponse:
    """Build PlayerAdvancedStatsResponse from database models."""
    advanced_stats = None
    if advanced:
        advanced_stats = AdvancedStats(
            ts_pct=advanced.ts_pct,
            efg_pct=advanced.efg_pct,
            usg_pct=advanced.usg_pct,
            off_rating=advanced.off_rating,
            def_rating=advanced.def_rating,
            net_rating=advanced.net_rating,
            pace=advanced.pace,
            pie=advanced.pie,
            ast_pct=advanced.ast_pct,
            ast_to=advanced.ast_to,
            oreb_pct=advanced.oreb_pct,
            dreb_pct=advanced.dreb_pct,
            reb_pct=advanced.reb_pct,
        )

    clutch_stats = None
    if clutch:
        clutch_stats = ClutchStats(
            games_played=clutch.games_played,
            minutes=clutch.minutes,
            pts=clutch.pts,
            fgm=clutch.fgm,
            fga=clutch.fga,
            fg_pct=clutch.fg_pct,
            fg3m=clutch.fg3m,
            fg3a=clutch.fg3a,
            fg3_pct=clutch.fg3_pct,
            ftm=clutch.ftm,
            fta=clutch.fta,
            ft_pct=clutch.ft_pct,
            ast=clutch.ast,
            reb=clutch.reb,
            stl=clutch.stl,
            blk=clutch.blk,
            tov=clutch.tov,
            plus_minus=clutch.plus_minus,
            net_rating=clutch.net_rating,
        )

    return PlayerAdvancedStatsResponse(
        id=player.id,
        nba_id=player.nba_id,
        name=player.name,
        position=player.position,
        team_abbreviation=player.team_abbreviation,
        season=season,
        advanced=advanced_stats,
        clutch=clutch_stats,
    )


def _build_defensive_profile(
    player: Player,
    defense: PlayerDefensiveStatsModel | None,
    season: str,
) -> PlayerDefensiveProfile:
    """Build PlayerDefensiveProfile from database model."""
    overall = None
    rim = None
    three_point = None
    iso_defense = None

    if defense:
        overall = DefenseZoneStats(
            d_fgm=defense.overall_d_fgm,
            d_fga=defense.overall_d_fga,
            d_fg_pct=defense.overall_d_fg_pct,
            normal_fg_pct=defense.overall_normal_fg_pct,
            pct_plusminus=defense.overall_pct_plusminus,
        )
        rim = DefenseZoneStats(
            d_fgm=defense.rim_d_fgm,
            d_fga=defense.rim_d_fga,
            d_fg_pct=defense.rim_d_fg_pct,
            normal_fg_pct=defense.rim_normal_fg_pct,
            pct_plusminus=defense.rim_pct_plusminus,
        )
        three_point = DefenseZoneStats(
            d_fgm=defense.three_pt_d_fgm,
            d_fga=defense.three_pt_d_fga,
            d_fg_pct=defense.three_pt_d_fg_pct,
            normal_fg_pct=defense.three_pt_normal_fg_pct,
            pct_plusminus=defense.three_pt_pct_plusminus,
        )
        iso_defense = IsoDefenseStats(
            poss=defense.iso_poss,
            pts=defense.iso_pts,
            fgm=defense.iso_fgm,
            fga=defense.iso_fga,
            ppp=defense.iso_ppp,
            fg_pct=defense.iso_fg_pct,
            percentile=defense.iso_percentile,
        )

    return PlayerDefensiveProfile(
        id=player.id,
        nba_id=player.nba_id,
        name=player.name,
        position=player.position,
        team_abbreviation=player.team_abbreviation,
        season=season,
        overall=overall,
        rim=rim,
        three_point=three_point,
        iso_defense=iso_defense,
    )


@router.get("/advanced", response_model=list[PlayerAdvancedStatsResponse])
@cache(expire=_ADVANCED_STATS_TTL)
async def get_advanced_stats(
    season: str | None = Query(default=None),
    limit: int = Query(default=50, le=500),
    offset: int = Query(default=0, ge=0),
    db: Session = Depends(get_db),
):
    """Get advanced stats for all players with pagination.

    Args:
        season: NBA season string
        limit: Number of results (max 500)
        offset: Number of results to skip
    """
    season = season or get_current_season()
    results = (
        db.query(Player, PlayerAdvancedStats, PlayerClutchStatsModel)
        .outerjoin(
            PlayerAdvancedStats,
            (Player.id == PlayerAdvancedStats.player_id)
            & (PlayerAdvancedStats.season == season),
        )
        .outerjoin(
            PlayerClutchStatsModel,
            (Player.id == PlayerClutchStatsModel.player_id)
            & (PlayerClutchStatsModel.season == season),
        )
        .filter(PlayerAdvancedStats.ts_pct.isnot(None))
        .order_by(desc(PlayerAdvancedStats.net_rating))
        .offset(offset)
        .limit(limit)
        .all()
    )

    return [
        _build_advanced_stats_response(player, advanced, clutch, season)
        for player, advanced, clutch in results
    ]


@router.get("/advanced/{player_id}", response_model=PlayerAdvancedStatsResponse)
async def get_player_advanced_stats(
    player_id: int,
    season: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get advanced stats for a single player.

    Args:
        player_id: Internal player ID
        season: NBA season string
    """
    season = season or get_current_season()
    result = (
        db.query(Player, PlayerAdvancedStats, PlayerClutchStatsModel)
        .outerjoin(
            PlayerAdvancedStats,
            (Player.id == PlayerAdvancedStats.player_id)
            & (PlayerAdvancedStats.season == season),
        )
        .outerjoin(
            PlayerClutchStatsModel,
            (Player.id == PlayerClutchStatsModel.player_id)
            & (PlayerClutchStatsModel.season == season),
        )
        .filter(Player.id == player_id)
        .first()
    )

    if not result:
        raise HTTPException(status_code=404, detail="Player not found")

    player, advanced, clutch = result
    return _build_advanced_stats_response(player, advanced, clutch, season)


@router.get("/shot-zones/{player_id}", response_model=PlayerShotZones)
async def get_player_shot_zones(
    player_id: int,
    season: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get shot zone distribution for a single player.

    Args:
        player_id: Internal player ID
        season: NBA season string
    """
    season = season or get_current_season()
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    shot_zones = (
        db.query(PlayerShotZonesModel)
        .filter(
            PlayerShotZonesModel.player_id == player_id,
            PlayerShotZonesModel.season == season,
        )
        .all()
    )

    if not shot_zones:
        raise HTTPException(
            status_code=404,
            detail=f"Shot zone data not found for player {player_id} in season {season}",
        )

    zones = [
        ShotZone(
            zone=sz.zone,
            fgm=sz.fgm,
            fga=sz.fga,
            fg_pct=sz.fg_pct,
            freq=sz.freq,
            league_avg=sz.league_avg,
        )
        for sz in shot_zones
    ]

    return PlayerShotZones(
        id=player.id,
        nba_id=player.nba_id,
        name=player.name,
        position=player.position,
        team_abbreviation=player.team_abbreviation,
        season=season,
        zones=zones,
    )


@router.get("/defense/leaderboard", response_model=list[PlayerDefensiveProfile])
@cache(expire=_ADVANCED_STATS_TTL)
async def get_defensive_leaderboard(
    season: str | None = Query(default=None),
    limit: int = Query(default=50, le=100),
    sort_by: Literal["rim", "overall", "three_point"] = Query(
        default="overall",
        description="Defensive category to sort by",
    ),
    db: Session = Depends(get_db),
):
    """Get defensive leaderboard sorted by the specified category's DFG% differential.

    Best defenders have the most negative pct_plusminus (they lower opponents' FG%).

    Args:
        season: NBA season string
        limit: Number of results (max 100)
        sort_by: Defensive category - 'rim', 'overall', or 'three_point'
    """
    season = season or get_current_season()
    # Determine sort column (most negative pct_plusminus = best defender)
    sort_column = {
        "rim": PlayerDefensiveStatsModel.rim_pct_plusminus,
        "overall": PlayerDefensiveStatsModel.overall_pct_plusminus,
        "three_point": PlayerDefensiveStatsModel.three_pt_pct_plusminus,
    }.get(sort_by, PlayerDefensiveStatsModel.overall_pct_plusminus)

    results = (
        db.query(Player, PlayerDefensiveStatsModel)
        .join(PlayerDefensiveStatsModel, Player.id == PlayerDefensiveStatsModel.player_id)
        .filter(PlayerDefensiveStatsModel.season == season)
        .filter(sort_column.isnot(None))
        .order_by(asc(sort_column))
        .limit(limit)
        .all()
    )

    return [
        _build_defensive_profile(player, defense, season)
        for player, defense in results
    ]


@router.get("/defense/{player_id}", response_model=PlayerDefensiveProfile)
async def get_player_defensive_profile(
    player_id: int,
    season: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get defensive profile for a single player.

    Args:
        player_id: Internal player ID
        season: NBA season string
    """
    season = season or get_current_season()
    result = (
        db.query(Player, PlayerDefensiveStatsModel)
        .outerjoin(
            PlayerDefensiveStatsModel,
            (Player.id == PlayerDefensiveStatsModel.player_id)
            & (PlayerDefensiveStatsModel.season == season),
        )
        .filter(Player.id == player_id)
        .first()
    )

    if not result:
        raise HTTPException(status_code=404, detail="Player not found")

    player, defense = result
    return _build_defensive_profile(player, defense, season)
