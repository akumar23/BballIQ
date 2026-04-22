"""Players API routes.

A few endpoints in here are on the hot path for the dashboard:

* ``/available`` powers the player-card selector and is called on every
  dashboard load. 300s TTL via fastapi-cache2 — the underlying data (which
  players have career stats rows) only changes when the nightly refresh
  runs.
* ``/{player_id}`` powers the player detail view. 60s TTL — short enough
  that freshly-seeded data shows up quickly, long enough to absorb
  bursty reads.
* ``/{player_id}/games`` (gamelog) is intentionally NOT cached — responses
  are per-player large and the TTL wouldn't help much for the
  low-cardinality access pattern.
"""

from __future__ import annotations

import logging

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi_cache.decorator import cache
from sqlalchemy import func
from sqlalchemy.exc import DBAPIError, ProgrammingError
from sqlalchemy.orm import Session

from app.core.season import get_current_season
from app.db.session import get_db
from app.models import (
    GameStats,
    Player,
    PlayerCareerStats,
    SeasonStats,
)
from app.schemas.player import (
    PlayerCardOption,
    PlayerCardOptionPage,
    PlayerDetail,
    PlayerList,
    PlayerSearchResult,
)
from app.schemas.player_card import PlayerCardData
from app.services.player_card import PlayerCardService

logger = logging.getLogger(__name__)

router = APIRouter()

# Per-player detail is a small fixed-size payload; 60s is plenty.
_PLAYER_DETAIL_TTL = 60
# ``/available`` data only changes on the nightly refresh; 5 min is safe.
_AVAILABLE_TTL = 300


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


@router.get("/available")
@cache(expire=_AVAILABLE_TTL)
async def get_available_players(
    limit: int | None = Query(
        default=None,
        ge=1,
        le=500,
        description="Page size. Pass together with ``offset`` to opt into the paginated envelope.",
    ),
    offset: int | None = Query(
        default=None,
        ge=0,
        description=(
            "Page offset. Passing either ``limit`` or ``offset`` switches "
            "the response to the paginated envelope."
        ),
    ),
    db: Session = Depends(get_db),
) -> list[PlayerCardOption] | PlayerCardOptionPage:
    """Get all players with every season they have data for, for the card selector.

    Returns a flat list sorted by ``player.name`` then ``season`` descending.
    Each entry represents a distinct player+season combination that has
    career stats in the database.

    Response shape:

    * If neither ``limit`` nor ``offset`` is passed, returns a bare list
      (legacy shape — the frontend still consumes this).
    * If either is passed, returns ``{"items": [...], "total": N, "limit": L, "offset": O}``.

    TODO(api-v2): remove the legacy bare-array branch once the frontend is
    migrated to always paginate. Tracked in follow-up ticket.
    """
    paginated = limit is not None or offset is not None

    base_query = (
        db.query(Player, PlayerCareerStats.season)
        .join(PlayerCareerStats, Player.id == PlayerCareerStats.player_id)
        .filter(Player.active == True)
        .order_by(Player.name, PlayerCareerStats.season.desc())
    )

    if not paginated:
        rows = base_query.all()
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

    effective_limit = limit if limit is not None else 50
    effective_offset = offset if offset is not None else 0

    # Count before slicing. Use the same join so ``total`` matches the set
    # being paginated, not ``SELECT COUNT(*) FROM players``.
    total = (
        db.query(func.count())
        .select_from(Player)
        .join(PlayerCareerStats, Player.id == PlayerCareerStats.player_id)
        .filter(Player.active.is_(True))
        .scalar()
    ) or 0

    page_rows = base_query.offset(effective_offset).limit(effective_limit).all()

    items = [
        PlayerCardOption(
            id=player.id,
            name=player.name,
            position=player.position,
            team_abbreviation=player.team_abbreviation,
            season=season,
        )
        for player, season in page_rows
    ]

    return PlayerCardOptionPage(
        items=items,
        total=int(total),
        limit=effective_limit,
        offset=effective_offset,
    )


@router.get("/search", response_model=list[PlayerSearchResult])
async def search_players(
    q: str = Query(..., min_length=1, max_length=100, description="Free-form name query."),
    limit: int = Query(default=20, ge=1, le=50),
    db: Session = Depends(get_db),
) -> list[PlayerSearchResult]:
    """Fuzzy search on players by name.

    Uses Postgres ``pg_trgm`` trigram similarity when available (see the
    ``ix_players_name_trgm`` migration). Falls back to a case-insensitive
    substring match if the extension isn't installed — less forgiving on
    typos but still useful and keeps the endpoint responsive in tests
    or environments where the extension hasn't been provisioned.
    """
    q_normalized = q.strip()
    if not q_normalized:
        return []

    try:
        similarity = func.similarity(Player.name, q_normalized)
        rows = (
            db.query(Player, similarity.label("similarity"))
            .filter(Player.active.is_(True))
            .filter(Player.name.op("%")(q_normalized))
            .order_by(similarity.desc())
            .limit(limit)
            .all()
        )
        return [
            PlayerSearchResult(
                id=player.id,
                nba_id=player.nba_id,
                name=player.name,
                position=player.position,
                team_abbreviation=player.team_abbreviation,
                similarity=float(score) if score is not None else None,
            )
            for player, score in rows
        ]
    except (ProgrammingError, DBAPIError) as exc:
        # pg_trgm extension missing (undefined_function on ``similarity``
        # / ``%`` operator). Roll back and fall through to the
        # portable ILIKE path so the endpoint still returns something
        # useful instead of 500-ing.
        db.rollback()
        logger.warning(
            "pg_trgm unavailable for /players/search, falling back to ILIKE: %s",
            exc,
        )

    # Fallback path. No ordering by similarity is possible here, so we
    # stabilise by name to give deterministic responses.
    like_pattern = f"%{q_normalized}%"
    fallback_rows = (
        db.query(Player)
        .filter(Player.active.is_(True))
        .filter(Player.name.ilike(like_pattern))
        .order_by(Player.name)
        .limit(limit)
        .all()
    )
    return [
        PlayerSearchResult(
            id=player.id,
            nba_id=player.nba_id,
            name=player.name,
            position=player.position,
            team_abbreviation=player.team_abbreviation,
            similarity=None,
        )
        for player in fallback_rows
    ]


@router.get("/{player_id}", response_model=PlayerDetail)
@cache(expire=_PLAYER_DETAIL_TTL)
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
