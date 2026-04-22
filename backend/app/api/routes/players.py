from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.season import get_current_season
from app.db.session import get_db
from app.models import (
    GameStats,
    Player,
    PlayerCareerStats,
    SeasonStats,
)
from app.schemas.player import PlayerCardOption, PlayerDetail, PlayerList
from app.schemas.player_card import PlayerCardData
from app.services.player_card import PlayerCardService

router = APIRouter()


@router.get("/seasons", response_model=list[str])
async def get_seasons(db: Session = Depends(get_db)):
    """Get all seasons available in the database, sorted descending."""
    rows = (
        db.query(SeasonStats.season)
        .distinct()
        .order_by(SeasonStats.season.desc())
        .all()
    )
    return [r.season for r in rows]


@router.get("", response_model=list[PlayerList])
async def get_players(
    season: str | None = Query(default=None),
    position: str | None = Query(default=None),
    team: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0),
    db: Session = Depends(get_db),
):
    """Get all players with their current metrics."""
    season = season or get_current_season()
    query = (
        db.query(Player, SeasonStats)
        .outerjoin(
            SeasonStats,
            (SeasonStats.player_id == Player.id) & (SeasonStats.season == season),
        )
        .filter(Player.active == True)
    )

    if position:
        query = query.filter(Player.position.ilike(f"%{position}%"))
    if team:
        query = query.filter(Player.team_abbreviation == team.upper())

    rows = query.offset(offset).limit(limit).all()

    return [
        PlayerList(
            id=player.id,
            nba_id=player.nba_id,
            name=player.name,
            position=player.position,
            team_abbreviation=player.team_abbreviation,
            metrics={
                "offensive_metric": season_stat.offensive_metric if season_stat else None,
                "defensive_metric": season_stat.defensive_metric if season_stat else None,
                "overall_metric": season_stat.overall_metric if season_stat else None,
                "offensive_percentile": season_stat.offensive_percentile if season_stat else None,
                "defensive_percentile": season_stat.defensive_percentile if season_stat else None,
            }
            if season_stat
            else None,
        )
        for player, season_stat in rows
    ]


@router.get("/available", response_model=list[PlayerCardOption])
async def get_available_players(
    db: Session = Depends(get_db),
):
    """Get all players with every season they have data for, for the card selector.

    Returns a flat list sorted by player name then season descending.
    Each entry represents a distinct player+season combination that has
    career stats in the database.
    """
    rows = (
        db.query(Player, PlayerCareerStats.season)
        .join(PlayerCareerStats, Player.id == PlayerCareerStats.player_id)
        .filter(Player.active == True)
        .order_by(Player.name, PlayerCareerStats.season.desc())
        .all()
    )

    return [
        PlayerCardOption(
            id=player.id,
            name=player.name,
            position=player.position,
            team_abbreviation=player.team_abbreviation,
            season=season,
        )
        for player, season in rows
    ]


@router.get("/{player_id}", response_model=PlayerDetail)
async def get_player(
    player_id: int,
    season: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get a single player with detailed stats."""
    season = season or get_current_season()
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    season_stat = (
        db.query(SeasonStats)
        .filter(SeasonStats.player_id == player.id, SeasonStats.season == season)
        .first()
    )

    return PlayerDetail(
        id=player.id,
        nba_id=player.nba_id,
        name=player.name,
        position=player.position,
        team_abbreviation=player.team_abbreviation,
        season=season,
        games_played=season_stat.games_played if season_stat else None,
        metrics={
            "offensive_metric": season_stat.offensive_metric if season_stat else None,
            "defensive_metric": season_stat.defensive_metric if season_stat else None,
            "overall_metric": season_stat.overall_metric if season_stat else None,
            "offensive_percentile": season_stat.offensive_percentile if season_stat else None,
            "defensive_percentile": season_stat.defensive_percentile if season_stat else None,
        }
        if season_stat
        else None,
        tracking_stats={
            "touches": season_stat.total_touches if season_stat else None,
            "points_per_touch": season_stat.avg_points_per_touch if season_stat else None,
            "time_of_possession": season_stat.total_time_of_possession if season_stat else None,
            "deflections": season_stat.total_deflections if season_stat else None,
            "contested_shots": season_stat.total_contested_shots if season_stat else None,
        }
        if season_stat
        else None,
    )


@router.get("/{player_id}/games")
async def get_player_games(
    player_id: int,
    season: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get all game logs for a player in a given season, ordered by date descending."""
    season = season or get_current_season()
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    games = (
        db.query(GameStats)
        .filter(GameStats.player_id == player_id, GameStats.season == season)
        .order_by(GameStats.game_date.desc())
        .all()
    )

    return [
        {
            "game_date": g.game_date,
            "matchup": g.matchup,
            "wl": g.wl,
            "minutes": float(g.minutes) if g.minutes is not None else None,
            "points": g.points,
            "rebounds": g.rebounds,
            "assists": g.assists,
            "steals": g.steals,
            "blocks": g.blocks,
            "turnovers": g.turnovers,
            "fgm": g.fgm,
            "fga": g.fga,
            "fg_pct": float(g.fg_pct) if g.fg_pct is not None else None,
            "fg3m": g.fg3m,
            "fg3a": g.fg3a,
            "fg3_pct": float(g.fg3_pct) if g.fg3_pct is not None else None,
            "ftm": g.ftm,
            "fta": g.fta,
            "ft_pct": float(g.ft_pct) if g.ft_pct is not None else None,
            "plus_minus": g.plus_minus,
            "game_score": float(g.game_score) if g.game_score is not None else None,
            "offensive_rebounds": g.offensive_rebounds,
            "defensive_rebounds": g.defensive_rebounds,
        }
        for g in games
    ]


@router.get("/{player_id}/card", response_model=PlayerCardData)
async def get_player_card(
    player_id: int,
    season: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    """Get comprehensive aggregated data for the player card page."""
    season = season or get_current_season()
    service = PlayerCardService(db=db, player_id=player_id, season=season)
    return service.build()
