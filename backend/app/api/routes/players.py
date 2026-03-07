from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import Player, SeasonStats
from app.schemas.player import PlayerDetail, PlayerList

router = APIRouter()


@router.get("", response_model=list[PlayerList])
async def get_players(
    season: str = Query(default="2024-25"),
    position: str | None = Query(default=None),
    team: str | None = Query(default=None),
    limit: int = Query(default=100, le=500),
    offset: int = Query(default=0),
    db: Session = Depends(get_db),
):
    """Get all players with their current metrics."""
    query = db.query(Player).filter(Player.active == True)

    if position:
        query = query.filter(Player.position.ilike(f"%{position}%"))
    if team:
        query = query.filter(Player.team_abbreviation == team.upper())

    players = query.offset(offset).limit(limit).all()

    # Attach season stats/metrics to each player
    result = []
    for player in players:
        season_stat = (
            db.query(SeasonStats)
            .filter(SeasonStats.player_id == player.id, SeasonStats.season == season)
            .first()
        )

        player_data = PlayerList(
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
        result.append(player_data)

    return result


@router.get("/{player_id}", response_model=PlayerDetail)
async def get_player(
    player_id: int,
    season: str = Query(default="2024-25"),
    db: Session = Depends(get_db),
):
    """Get a single player with detailed stats."""
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
