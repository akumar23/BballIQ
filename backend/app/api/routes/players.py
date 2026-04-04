from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import (
    ContextualizedImpact,
    Player,
    PlayerAdvancedStats,
    PlayerCareerStats,
    PlayerComputedAdvanced,
    PlayerDefensiveStats,
    PlayerOnOffStats,
    PlayerShotZones,
    SeasonPlayTypeStats,
    SeasonStats,
)
from app.schemas.player import PlayerDetail, PlayerList, PlayerCardOption
from app.schemas.player_card import (
    CardAdvanced,
    CardCareerSeason,
    CardContextualized,
    CardDefenseZone,
    CardDefensive,
    CardImpact,
    CardIsoDefense,
    CardOnOff,
    CardPlayType,
    CardPlayTypes,
    CardRadar,
    CardShotZone,
    CardTraditional,
    PlayerCardData,
)

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


def _card_play_type(stats: SeasonPlayTypeStats, play_type: str) -> CardPlayType | None:
    poss = getattr(stats, f"{play_type}_poss", None)
    if poss is None:
        return None
    return CardPlayType(
        possessions=poss,
        ppp=getattr(stats, f"{play_type}_ppp", None),
        fg_pct=getattr(stats, f"{play_type}_fg_pct", None),
        frequency=getattr(stats, f"{play_type}_freq", None),
        ppp_percentile=getattr(stats, f"{play_type}_ppp_percentile", None),
    )


def _card_defense_zone(d_fg_pct, normal_fg_pct, pct_plusminus) -> CardDefenseZone | None:
    if d_fg_pct is None and normal_fg_pct is None and pct_plusminus is None:
        return None
    return CardDefenseZone(
        d_fg_pct=d_fg_pct,
        normal_fg_pct=normal_fg_pct,
        pct_plusminus=pct_plusminus,
    )


@router.get("/{player_id}/card", response_model=PlayerCardData)
async def get_player_card(
    player_id: int,
    season: str = Query(default="2024-25"),
    db: Session = Depends(get_db),
):
    """Get comprehensive aggregated data for the player card page."""
    player = db.query(Player).filter(Player.id == player_id).first()
    if not player:
        raise HTTPException(status_code=404, detail="Player not found")

    season_stat = (
        db.query(SeasonStats)
        .filter(SeasonStats.player_id == player_id, SeasonStats.season == season)
        .first()
    )
    current_career = (
        db.query(PlayerCareerStats)
        .filter(PlayerCareerStats.player_id == player_id, PlayerCareerStats.season == season)
        .first()
    )
    advanced = (
        db.query(PlayerAdvancedStats)
        .filter(PlayerAdvancedStats.player_id == player_id, PlayerAdvancedStats.season == season)
        .first()
    )
    computed = (
        db.query(PlayerComputedAdvanced)
        .filter(PlayerComputedAdvanced.player_id == player_id, PlayerComputedAdvanced.season == season)
        .first()
    )
    on_off = (
        db.query(PlayerOnOffStats)
        .filter(PlayerOnOffStats.player_id == player_id, PlayerOnOffStats.season == season)
        .first()
    )
    impact_ctx = (
        db.query(ContextualizedImpact)
        .filter(ContextualizedImpact.player_id == player_id, ContextualizedImpact.season == season)
        .first()
    )
    play_types = (
        db.query(SeasonPlayTypeStats)
        .filter(SeasonPlayTypeStats.player_id == player_id, SeasonPlayTypeStats.season == season)
        .first()
    )
    shot_zones = (
        db.query(PlayerShotZones)
        .filter(PlayerShotZones.player_id == player_id, PlayerShotZones.season == season)
        .all()
    )
    defense = (
        db.query(PlayerDefensiveStats)
        .filter(PlayerDefensiveStats.player_id == player_id, PlayerDefensiveStats.season == season)
        .first()
    )
    career_rows = (
        db.query(PlayerCareerStats)
        .filter(PlayerCareerStats.player_id == player_id)
        .order_by(PlayerCareerStats.season)
        .all()
    )

    # Traditional per-game stats from career (current season) + tov from season totals
    traditional = None
    gp = (
        (current_career.games_played if current_career else None)
        or (season_stat.games_played if season_stat else None)
        or 1
    )
    if current_career or season_stat:
        tov = None
        if season_stat and season_stat.total_turnovers:
            tov = Decimal(str(round(season_stat.total_turnovers / gp, 1)))
        traditional = CardTraditional(
            ppg=current_career.ppg if current_career else None,
            rpg=current_career.rpg if current_career else None,
            apg=current_career.apg if current_career else None,
            spg=current_career.spg if current_career else None,
            bpg=current_career.bpg if current_career else None,
            tov=tov,
            fg_pct=current_career.fg_pct if current_career else None,
            fg3_pct=current_career.fg3_pct if current_career else None,
            ft_pct=current_career.ft_pct if current_career else None,
            mpg=current_career.minutes if current_career else None,
            games_played=gp,
        )

    # Advanced and computed metrics
    advanced_stats = None
    if advanced or computed:
        advanced_stats = CardAdvanced(
            per=computed.per if computed else None,
            ts_pct=advanced.ts_pct if advanced else None,
            ws48=computed.ws_per_48 if computed else None,
            bpm=computed.bpm if computed else None,
            vorp=computed.vorp if computed else None,
            ortg=advanced.off_rating if advanced else None,
            drtg=advanced.def_rating if advanced else None,
            usg_pct=advanced.usg_pct if advanced else None,
            ows=computed.ows if computed else None,
            dws=computed.dws if computed else None,
        )

    # Radar percentiles
    radar = None
    if computed:
        radar = CardRadar(
            scoring=computed.radar_scoring,
            playmaking=computed.radar_playmaking,
            defense=computed.radar_defense,
            efficiency=computed.radar_efficiency,
            volume=computed.radar_volume,
            durability=computed.radar_durability,
            clutch=computed.radar_clutch,
            versatility=computed.radar_versatility,
        )

    # On/off and contextualized impact
    card_impact = None
    on_off_data = None
    if on_off:
        on_off_data = CardOnOff(
            on_ortg=on_off.on_court_off_rating,
            off_ortg=on_off.off_court_off_rating,
            on_drtg=on_off.on_court_def_rating,
            off_drtg=on_off.off_court_def_rating,
            net_swing=on_off.net_rating_diff,
        )
    ctx_data = None
    if impact_ctx:
        ctx_data = CardContextualized(
            raw_net_rtg=impact_ctx.raw_net_rating_diff,
            contextualized_net_rtg=impact_ctx.contextualized_net_impact,
            percentile=impact_ctx.impact_percentile,
        )
    if on_off_data or ctx_data:
        card_impact = CardImpact(on_off=on_off_data, contextualized=ctx_data)

    # Play type breakdown
    card_play_types = None
    if play_types:
        card_play_types = CardPlayTypes(
            isolation=_card_play_type(play_types, "isolation"),
            pnr_ball_handler=_card_play_type(play_types, "pnr_ball_handler"),
            pnr_roll_man=_card_play_type(play_types, "pnr_roll_man"),
            post_up=_card_play_type(play_types, "post_up"),
            spot_up=_card_play_type(play_types, "spot_up"),
            transition=_card_play_type(play_types, "transition"),
            cut=_card_play_type(play_types, "cut"),
            off_screen=_card_play_type(play_types, "off_screen"),
        )

    # Shot zones (per-game FGA)
    card_shot_zones = [
        CardShotZone(
            zone=sz.zone,
            fga_per_game=Decimal(str(round(sz.fga / gp, 1))) if sz.fga else None,
            fg_pct=sz.fg_pct,
            freq=sz.freq,
            league_avg=sz.league_avg,
        )
        for sz in shot_zones
    ]

    # Defensive profile
    card_defensive = None
    if defense:
        card_defensive = CardDefensive(
            overall=_card_defense_zone(
                defense.overall_d_fg_pct,
                defense.overall_normal_fg_pct,
                defense.overall_pct_plusminus,
            ),
            rim=_card_defense_zone(
                defense.rim_d_fg_pct,
                defense.rim_normal_fg_pct,
                defense.rim_pct_plusminus,
            ),
            three_point=_card_defense_zone(
                defense.three_pt_d_fg_pct,
                defense.three_pt_normal_fg_pct,
                defense.three_pt_pct_plusminus,
            ),
            iso_defense=CardIsoDefense(
                poss=defense.iso_poss,
                ppp=defense.iso_ppp,
                fg_pct=defense.iso_fg_pct,
                percentile=defense.iso_percentile,
            ) if defense.iso_poss else None,
        )

    # Career trajectory (traditional stats per season)
    card_career = [
        CardCareerSeason(
            season=row.season,
            ppg=row.ppg,
            rpg=row.rpg,
            apg=row.apg,
            fg_pct=row.fg_pct,
            fg3_pct=row.fg3_pct,
            ft_pct=row.ft_pct,
            minutes=row.minutes,
            games_played=row.games_played,
        )
        for row in career_rows
    ]

    return PlayerCardData(
        id=player.id,
        nba_id=player.nba_id,
        name=player.name,
        position=player.position,
        team_abbreviation=player.team_abbreviation,
        season=season,
        traditional=traditional,
        advanced=advanced_stats,
        radar=radar,
        impact=card_impact,
        play_types=card_play_types,
        shot_zones=card_shot_zones,
        defensive=card_defensive,
        career=card_career,
    )
