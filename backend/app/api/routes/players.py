from decimal import Decimal

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models import (
    ContextualizedImpact,
    Player,
    PlayerAdvancedStats,
    PlayerAllInOneMetrics,
    PlayerCareerStats,
    PlayerComputedAdvanced,
    PlayerDefensiveStats,
    PlayerMatchups,
    PlayerOnOffStats,
    PlayerShootingTracking,
    PlayerShotZones,
    SeasonPlayTypeStats,
    SeasonStats,
)
from app.models.clutch_stats import PlayerClutchStats
from app.models.per_75_stats import Per75Stats
from app.schemas.player import PlayerDetail, PlayerList, PlayerCardOption
from app.schemas.player_card import (
    CardAdvanced,
    CardAllInOne,
    CardCareerSeason,
    CardChampionship,
    CardChampionshipPillar,
    CardContextualized,
    CardDefenseZone,
    CardDefensive,
    CardImpact,
    CardIsoDefense,
    CardAdjustmentStep,
    CardDefenseOverview,
    CardLineup,
    CardLineupContext,
    CardLuckAdjusted,
    CardMatchup,
    CardOnOff,
    CardOpponentTierEntry,
    CardPlayoffProjection,
    CardPlayType,
    CardPlayTypes,
    CardPortability,
    CardRadar,
    CardSchemeScore,
    CardShotZone,
    CardTraditional,
    CardWithoutTeammate,
    PlayerCardData,
)
from app.services.championship import ChampionshipCalculator
from app.services.luck_adjusted import LuckAdjustedCalculator
from app.services.metrics_utils import safe_float, to_decimal
from app.services.opponent_tier import TIER_WEIGHTS, OpponentTierCalculator
from app.services.portability import PortabilityCalculator
from app.services.scheme_compatibility import SchemeCompatibilityCalculator

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


class _EmptyObj:
    """Stand-in for missing DB models — returns None/0 for any attribute."""
    def __getattr__(self, name):
        return None

def _empty_obj():
    return _EmptyObj()


def _build_defense_overview(season_stat, defense, gp) -> CardDefenseOverview | None:
    """Build defense overview from season stats and defensive stats."""
    if not season_stat and not defense:
        return None
    gp = max(1, gp)
    total_min = safe_float(season_stat.total_minutes) if season_stat else 0
    min_per_game = total_min / gp if gp > 0 else 0

    # Contest rate: contested shots per minute
    contested = (
        (safe_float(season_stat.total_contested_shots_2pt) + safe_float(season_stat.total_contested_shots_3pt))
        if season_stat else 0
    )
    contest_rate = to_decimal(contested / total_min * 36, "0.01") if total_min > 0 else None

    # Steal/block rates per 36 minutes
    stl_total = safe_float(season_stat.total_steals) if season_stat else 0
    blk_total = safe_float(season_stat.total_blocks) if season_stat else 0
    stl_rate = to_decimal(stl_total / total_min * 36, "0.01") if total_min > 0 else None
    blk_rate = to_decimal(blk_total / total_min * 36, "0.01") if total_min > 0 else None

    # Deflections per game
    defl = safe_float(season_stat.total_deflections) if season_stat else 0
    defl_pg = to_decimal(defl / gp, "0.01") if gp > 0 else None

    # Rim contests per game
    rim_contests = safe_float(defense.rim_d_fga) if defense else 0
    rim_cpg = to_decimal(rim_contests / gp, "0.01") if gp > 0 else None

    return CardDefenseOverview(
        contest_rate=contest_rate,
        stl_rate=stl_rate,
        blk_rate=blk_rate,
        deflections_per_game=defl_pg,
        rim_contests_per_game=rim_cpg,
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
        # Build adjustment waterfall from stored contextualized impact data
        adjustments = []
        cumulative = safe_float(impact_ctx.raw_net_rating_diff)
        adjustments.append(CardAdjustmentStep(
            name="Raw On/Off Net Rtg",
            value=impact_ctx.raw_net_rating_diff,
            cumulative=to_decimal(cumulative),
            explanation="Baseline team net rating differential when player is on vs off court",
        ))
        tm_adj = safe_float(impact_ctx.teammate_adjustment)
        if tm_adj != 0:
            cumulative -= tm_adj
            adjustments.append(CardAdjustmentStep(
                name="Teammate Quality",
                value=to_decimal(-tm_adj),
                cumulative=to_decimal(cumulative),
                explanation=f"Avg teammate net rating: {impact_ctx.avg_teammate_net_rating}",
            ))
        opp_factor = safe_float(impact_ctx.opponent_quality_factor)
        if opp_factor != 0 and opp_factor != 1.0:
            old_cum = cumulative
            cumulative = cumulative * opp_factor
            adjustments.append(CardAdjustmentStep(
                name="Opponent Quality",
                value=to_decimal(cumulative - old_cum),
                cumulative=to_decimal(cumulative),
                explanation=f"Pct minutes vs starters: {impact_ctx.pct_minutes_vs_starters}",
            ))
        rel = safe_float(impact_ctx.reliability_factor)
        if rel != 0 and rel != 1.0:
            old_cum = cumulative
            cumulative = cumulative * rel
            adjustments.append(CardAdjustmentStep(
                name="Reliability",
                value=to_decimal(cumulative - old_cum),
                cumulative=to_decimal(cumulative),
                explanation=f"Minutes: {impact_ctx.total_on_court_minutes}, factor: {impact_ctx.reliability_factor}",
            ))

        ctx_data = CardContextualized(
            raw_net_rtg=impact_ctx.raw_net_rating_diff,
            contextualized_net_rtg=impact_ctx.contextualized_net_impact,
            percentile=impact_ctx.impact_percentile,
            adjustments=adjustments,
        )

    # Actual wins from team record
    actual_wins = None
    if season_stat and player.team_abbreviation:
        from sqlalchemy import func
        team_total_plus_minus = (
            db.query(func.sum(SeasonStats.total_plus_minus))
            .join(Player, Player.id == SeasonStats.player_id)
            .filter(Player.team_abbreviation == player.team_abbreviation, SeasonStats.season == season)
            .scalar()
        )
        # Rough estimate: team wins ≈ 41 + (total_plus_minus / (gp * 5)) * 0.03 * 82
        # Simpler: use games played as proxy if plus_minus not useful
        team_gp_max = (
            db.query(func.max(SeasonStats.games_played))
            .join(Player, Player.id == SeasonStats.player_id)
            .filter(Player.team_abbreviation == player.team_abbreviation, SeasonStats.season == season)
            .scalar()
        )
        actual_wins = team_gp_max  # Placeholder - real wins need team record table

    if on_off_data or ctx_data:
        card_impact = CardImpact(on_off=on_off_data, contextualized=ctx_data, actual_wins=actual_wins)

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
            overview=_build_defense_overview(season_stat, defense, gp),
        )

    # Career trajectory — merge career stats with computed advanced per season
    computed_by_season = {
        row.season: row
        for row in db.query(PlayerComputedAdvanced)
        .filter(PlayerComputedAdvanced.player_id == player_id)
        .all()
    }
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
            per=computed_by_season[row.season].per if row.season in computed_by_season else None,
            ws48=computed_by_season[row.season].ws_per_48 if row.season in computed_by_season else None,
            bpm=computed_by_season[row.season].bpm if row.season in computed_by_season else None,
        )
        for row in career_rows
    ]

    # ------ New data: all-in-one metrics ------
    all_in_one_row = (
        db.query(PlayerAllInOneMetrics)
        .filter(PlayerAllInOneMetrics.player_id == player_id, PlayerAllInOneMetrics.season == season)
        .first()
    )
    card_all_in_one = None
    if all_in_one_row:
        card_all_in_one = CardAllInOne(
            rapm=all_in_one_row.rapm, rapm_offense=all_in_one_row.rapm_offense, rapm_defense=all_in_one_row.rapm_defense,
            rpm=all_in_one_row.rpm, rpm_offense=all_in_one_row.rpm_offense, rpm_defense=all_in_one_row.rpm_defense,
            epm=all_in_one_row.epm, epm_offense=all_in_one_row.epm_offense, epm_defense=all_in_one_row.epm_defense,
            raptor=all_in_one_row.raptor, raptor_offense=all_in_one_row.raptor_offense, raptor_defense=all_in_one_row.raptor_defense,
            lebron=all_in_one_row.lebron, lebron_offense=all_in_one_row.lebron_offense, lebron_defense=all_in_one_row.lebron_defense,
            darko=all_in_one_row.darko, darko_offense=all_in_one_row.darko_offense, darko_defense=all_in_one_row.darko_defense,
        )

    # ------ New data: matchup log (top 5) ------
    matchup_rows = (
        db.query(PlayerMatchups)
        .filter(PlayerMatchups.player_id == player_id, PlayerMatchups.season == season)
        .order_by(PlayerMatchups.partial_poss.desc())
        .limit(5)
        .all()
    )
    card_matchups = [
        CardMatchup(
            opponent=m.off_player_name,
            possessions=m.partial_poss,
            dfg_pct=m.matchup_fg_pct,
            pts_allowed=m.player_pts,
        )
        for m in matchup_rows
    ]

    # ------ Fetch extra models needed for custom metrics ------
    shooting_tracking = (
        db.query(PlayerShootingTracking)
        .filter(PlayerShootingTracking.player_id == player_id, PlayerShootingTracking.season == season)
        .first()
    )
    clutch_stats = (
        db.query(PlayerClutchStats)
        .filter(PlayerClutchStats.player_id == player_id, PlayerClutchStats.season == season)
        .first()
    )
    per75 = (
        db.query(Per75Stats)
        .filter(Per75Stats.season == season)
        .join(SeasonStats, SeasonStats.id == Per75Stats.season_stats_id)
        .filter(SeasonStats.player_id == player_id)
        .first()
    )

    # ------ Compute: Scheme Compatibility ------
    card_scheme_scores: list[CardSchemeScore] = []
    scheme_dict: dict | None = None
    if play_types and advanced and per75 and shooting_tracking:
        sz_list = shot_zones or []
        scheme_calc = SchemeCompatibilityCalculator(
            play_types=play_types,
            advanced=advanced,
            per75=per75,
            shooting=shooting_tracking,
            shot_zones=sz_list,
        )
        scheme_dict = scheme_calc.calculate_all()
        for name, val in scheme_dict.items():
            if name != "scheme_flexibility":
                card_scheme_scores.append(
                    CardSchemeScore(scheme=name, fit_score=to_decimal(val))
                )

    # ------ Compute: Portability Index ------
    card_portability = None
    portability_score = 50.0
    if season_stat and play_types and advanced:
        all_matchups = (
            db.query(PlayerMatchups)
            .filter(PlayerMatchups.player_id == player_id, PlayerMatchups.season == season)
            .all()
        )
        # Build position lookup for switchability
        all_player_positions = {
            p.nba_id: p.position
            for p in db.query(Player.nba_id, Player.position).all()
        }

        port_calc = PortabilityCalculator(
            season_stats=season_stat,
            play_types=play_types,
            shooting_tracking=shooting_tracking or _empty_obj(),
            advanced=advanced,
            on_off=on_off or _empty_obj(),
            per75=per75 or _empty_obj(),
            matchups=all_matchups,
            all_players_positions=all_player_positions,
            scheme_scores=scheme_dict,
        )
        port_result = port_calc.calculate()
        portability_score = port_result.portability_index

        card_portability = CardPortability(
            index=to_decimal(port_result.portability_index),
            grade=port_result.grade,
            self_creation=to_decimal(port_result.self_creation),
            scheme_flexibility=to_decimal(port_result.scheme_flexibility),
            switchability=to_decimal(port_result.switchability),
            low_dependency=to_decimal(port_result.low_dependency),
            unassisted_rate_score=to_decimal(port_result.unassisted_rate_score),
            self_created_ppp_score=to_decimal(port_result.self_created_ppp_score),
            gravity_score=to_decimal(port_result.gravity_score),
            creation_volume_score=to_decimal(port_result.creation_volume_score),
            positions_guarded={
                k: to_decimal(v) if v is not None else None
                for k, v in port_result.positions_guarded.items()
            },
            scheme_scores=card_scheme_scores,
        )

    # ------ Compute: Championship Index ------
    card_championship = None
    if season_stat and advanced:
        champ_calc = ChampionshipCalculator(
            season_stats=season_stat,
            advanced=advanced,
            play_types=play_types or _empty_obj(),
            clutch_stats=clutch_stats or _empty_obj(),
            on_off=on_off or _empty_obj(),
            computed_advanced=computed or _empty_obj(),
            all_in_one=all_in_one_row,
            career_stats=career_rows,
            portability_score=portability_score,
        )
        champ_result = champ_calc.calculate()
        # Playoff projection from the calculator's internal computation
        reg_ppg = safe_float(season_stat.total_points) / max(1, gp)
        reg_ts = safe_float(advanced.ts_pct) if advanced else 0.55
        usg = safe_float(advanced.usg_pct, 0.20) if advanced else 0.20
        ts_drop = 0.010 if usg >= 0.28 else (0.018 if usg >= 0.22 else 0.028)
        proj_ts = reg_ts - ts_drop
        proj_ppg = reg_ppg * ((usg + (0.02 if usg >= 0.25 else 0)) / max(0.01, usg)) * (proj_ts / max(0.01, reg_ts))

        playoff_proj = CardPlayoffProjection(
            projected_ppg=to_decimal(proj_ppg),
            projected_ts=to_decimal(proj_ts, "0.001"),
            reg_ppg=to_decimal(reg_ppg),
            reg_ts=to_decimal(reg_ts, "0.001"),
        )

        card_championship = CardChampionship(
            index=to_decimal(champ_result.championship_index),
            tier=champ_result.tier,
            win_probability=to_decimal(champ_result.win_probability, "0.0001"),
            multiplier_vs_base=to_decimal(champ_result.multiplier_vs_base),
            pillars=[
                CardChampionshipPillar(name="Playoff Scoring", score=to_decimal(champ_result.playoff_scoring), weight=to_decimal(0.25)),
                CardChampionshipPillar(name="Two-Way Impact", score=to_decimal(champ_result.two_way_impact), weight=to_decimal(0.20)),
                CardChampionshipPillar(name="Clutch Performance", score=to_decimal(champ_result.clutch_performance), weight=to_decimal(0.15)),
                CardChampionshipPillar(name="Portability", score=to_decimal(champ_result.portability), weight=to_decimal(0.15)),
                CardChampionshipPillar(name="Durability", score=to_decimal(champ_result.durability), weight=to_decimal(0.10)),
                CardChampionshipPillar(name="Experience & Arc", score=to_decimal(champ_result.experience_arc), weight=to_decimal(0.10)),
                CardChampionshipPillar(name="Supporting Cast", score=to_decimal(champ_result.supporting_cast), weight=to_decimal(0.05)),
            ],
            playoff_projection=playoff_proj,
        )

    # ------ Compute: Luck-Adjusted Metrics ------
    card_luck = None
    if on_off and season_stat and clutch_stats:
        # Get team stats for Pythagorean wins
        from app.models.season_stats import SeasonStats as SS
        team_season = (
            db.query(SS)
            .filter(SS.season == season)
            .join(Player, Player.id == SS.player_id)
            .filter(Player.team_abbreviation == player.team_abbreviation)
            .all()
        )
        team_pts = sum(safe_float(s.total_points) for s in team_season)
        team_gp = max(1, max((s.games_played or 0) for s in team_season)) if team_season else 82

        league_pace = safe_float(advanced.pace) if advanced else 100.0

        luck_calc = LuckAdjustedCalculator()
        team_stats_dict = {"pts_for": team_pts / team_gp * 100, "pts_against": team_pts / team_gp * 100, "games": team_gp}

        # Use on/off ratings for a better estimate
        on_ortg = safe_float(on_off.on_court_off_rating)
        on_drtg = safe_float(on_off.on_court_def_rating)
        if on_ortg > 0 and on_drtg > 0:
            team_stats_dict["pts_for"] = on_ortg
            team_stats_dict["pts_against"] = on_drtg

        luck_result = luck_calc.calculate_all(
            on_off=on_off,
            season_stats=season_stat,
            clutch_stats=clutch_stats,
            team_stats=team_stats_dict,
            league_pace=league_pace,
        )
        card_luck = CardLuckAdjusted(
            x_wins=to_decimal(luck_result["x_wins"]),
            clutch_epa=to_decimal(luck_result["clutch_epa"]),
            clutch_epa_per_game=to_decimal(luck_result["clutch_epa_per_game"]),
            garbage_time_ppg=to_decimal(luck_result["garbage_time_ppg"]),
        )

    # ------ Compute: Opponent Tier Performance ------
    card_opponent_tiers: list[CardOpponentTierEntry] = []
    if matchup_rows:
        # Fetch all matchups for this player (not just top 5)
        all_player_matchups = (
            db.query(PlayerMatchups)
            .filter(PlayerMatchups.player_id == player_id, PlayerMatchups.season == season)
            .all()
        )

        # Build tier lookup from all-in-one metrics across all players
        all_aio = {
            row.player_id: row
            for row in db.query(PlayerAllInOneMetrics).filter(PlayerAllInOneMetrics.season == season).all()
        }
        all_comp = {
            row.player_id: row
            for row in db.query(PlayerComputedAdvanced).filter(PlayerComputedAdvanced.season == season).all()
        }
        all_ss = {
            row.player_id: row
            for row in db.query(SeasonStats).filter(SeasonStats.season == season).all()
        }

        tier_calc = OpponentTierCalculator()
        opponent_tiers = tier_calc.assign_tiers(all_aio, all_comp, all_ss)

        tier_perf = tier_calc.performance_by_tier(player_id, all_player_matchups, opponent_tiers)

        for tier_name in ["Elite", "Quality", "Role", "Bench"]:
            data = tier_perf.get(tier_name)
            if data:
                card_opponent_tiers.append(CardOpponentTierEntry(
                    tier=tier_name,
                    possessions=data["possessions"],
                    dfg_pct=to_decimal(data["dfg_pct"], "0.001"),
                    ppp_allowed=to_decimal(data["ppp_allowed"], "0.001"),
                    weight=to_decimal(TIER_WEIGHTS[tier_name]),
                ))

    # ------ Compute: Lineup Context ------
    card_lineup_ctx = None
    if player.nba_id:
        from app.services.nba_data import NBADataService
        # Query stored lineup data — the LineupData from on/off fetch
        # Use the lineup data already in the on_off_stats context
        from sqlalchemy import text
        # Query top 5 lineups containing this player from lineup data
        # We need to use the lineup model or raw lineup stats
        # For now, build from the DB lineup cross-join approach:
        lineup_rows = (
            db.execute(text("""
                SELECT GROUP_ID, GROUP_NAME, MIN as minutes, PLUS_MINUS,
                       OFF_RATING, DEF_RATING, NET_RATING, GP
                FROM lineup_stats
                WHERE GROUP_NAME LIKE :pname AND season = :season
                ORDER BY MIN DESC LIMIT 5
            """), {"pname": f"%{player.name.split()[-1]}%", "season": season})
            .fetchall()
        ) if False else []  # Skip raw SQL — not available without lineup_stats table

        # Simpler: use the existing on/off data to build without-top-teammate
        without_top_tm = None
        if on_off:
            without_top_tm = CardWithoutTeammate(
                teammate="(team without player)",
                net_rtg=on_off.off_court_net_rating,
                minutes=on_off.off_court_minutes,
            )

        card_lineup_ctx = CardLineupContext(
            top_lineups=[],
            without_top_teammate=without_top_tm,
        )

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
        all_in_one=card_all_in_one,
        matchup_log=card_matchups,
        luck_adjusted=card_luck,
        opponent_tiers=card_opponent_tiers,
        scheme_compatibility=card_scheme_scores,
        portability=card_portability,
        championship=card_championship,
        lineup_context=card_lineup_ctx,
    )
