"""Service layer for the player card endpoint.

Orchestrates all database queries and computation (portability, championship,
luck-adjusted, scheme compatibility, opponent tiers, lineup context) required
to build the comprehensive PlayerCardData response.
"""

from __future__ import annotations

import logging
import math
from decimal import Decimal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import (
    ContextualizedImpact,
    DarkoHistory,
    LineupStats,
    Player,
    PlayerAdvancedStats,
    PlayerAllInOneMetrics,
    PlayerCareerStats,
    PlayerComputedAdvanced,
    PlayerConsistencyStats,
    PlayerDefenderDistanceShooting,
    PlayerDefensivePlayTypes,
    PlayerDefensiveStats,
    PlayerMatchups,
    PlayerOnOffStats,
    PlayerOpponentShooting,
    PlayerPassingStats,
    PlayerReboundingTracking,
    PlayerShootingTracking,
    PlayerShotZones,
    PlayerSpeedDistance,
    PlayerTouchesBreakdown,
    SeasonPlayTypeStats,
    SeasonStats,
)
from app.models.clutch_stats import PlayerClutchStats
from app.models.game_stats import GameStats
from app.models.per_75_stats import Per75Stats
from app.schemas.player_card import (
    CardAdjustmentStep,
    CardAdvanced,
    CardAllInOne,
    CardCareerSeason,
    CardChampionship,
    CardChampionshipPillar,
    CardConsistency,
    CardContestConversion,
    CardContextualized,
    CardDefenderDistanceEntry,
    CardDefenseOverview,
    CardDefenseZone,
    CardDefensive,
    CardDefensivePlayType,
    CardDefensivePlayTypes,
    CardDefensiveTerrain,
    CardFrictionEfficiency,
    CardGameLog,
    CardGravityIndex,
    CardImpact,
    CardIsoDefense,
    CardLateSeasonTrend,
    CardLeverageTs,
    CardLineup,
    CardLineupBuoyancy,
    CardLineupContext,
    CardLuckAdjusted,
    CardMatchup,
    CardMileProduction,
    CardOnOff,
    CardOpponentShooting,
    CardOpponentShootingBucket,
    CardOpponentTierEntry,
    CardPassFunnel,
    CardPassing,
    CardPlayoffProjection,
    CardPlayType,
    CardPlayTypes,
    CardPortability,
    CardPossessionDwell,
    CardRadar,
    CardReboundingTracking,
    CardRimGravity,
    CardSchemeRobustness,
    CardSchemeScore,
    CardShotDiet,
    CardShotZone,
    CardSpeedDistance,
    CardTeammateDependency,
    CardTouchesBreakdown,
    CardTouchKind,
    CardTraditional,
    CardWithoutTeammate,
    PlayerCardData,
)
from app.services.championship import ChampionshipCalculator
from app.services.luck_adjusted import LuckAdjustedCalculator
from app.services.metrics_utils import safe_float, to_decimal
from app.services.opponent_tier import TIER_WEIGHTS, OpponentTierCalculator
from app.services.portability import PortabilityCalculator
from app.services.redis_cache import redis_cache
from app.services.scheme_compatibility import SchemeCompatibilityCalculator

logger = logging.getLogger(__name__)


class _EmptyObj:
    """Stand-in for missing DB models -- returns None for any attribute."""

    def __getattr__(self, name: str):
        if name.startswith("_"):
            raise AttributeError(name)
        logger.debug("_EmptyObj: accessed missing attribute %r", name)
        return None

    def __repr__(self) -> str:
        return "<_EmptyObj>"


def _empty_obj() -> _EmptyObj:
    return _EmptyObj()


# ---------------------------------------------------------------------------
# Helper builders
# ---------------------------------------------------------------------------


def _build_defense_overview(
    season_stat: SeasonStats | None,
    defense: PlayerDefensiveStats | None,
    gp: int,
    rank: int | None = None,
) -> CardDefenseOverview | None:
    """Build defense overview from season stats and defensive stats."""
    if not season_stat and not defense:
        return None
    gp = max(1, gp)
    total_min = safe_float(season_stat.total_minutes) if season_stat else 0
    min_per_game = total_min / gp if gp > 0 else 0  # noqa: F841

    contested = (
        (
            safe_float(season_stat.total_contested_shots_2pt)
            + safe_float(season_stat.total_contested_shots_3pt)
        )
        if season_stat
        else 0
    )
    contest_rate = (
        to_decimal(contested / total_min * 36, "0.01") if total_min > 0 else None
    )

    stl_total = safe_float(season_stat.total_steals) if season_stat else 0
    blk_total = safe_float(season_stat.total_blocks) if season_stat else 0
    stl_rate = (
        to_decimal(stl_total / total_min * 36, "0.01") if total_min > 0 else None
    )
    blk_rate = (
        to_decimal(blk_total / total_min * 36, "0.01") if total_min > 0 else None
    )

    defl = safe_float(season_stat.total_deflections) if season_stat else 0
    defl_pg = to_decimal(defl / gp, "0.01") if gp > 0 else None

    rim_contests = safe_float(defense.rim_d_fga) if defense else 0
    rim_cpg = to_decimal(rim_contests / gp, "0.01") if gp > 0 else None

    return CardDefenseOverview(
        contest_rate=contest_rate,
        stl_rate=stl_rate,
        blk_rate=blk_rate,
        deflections_per_game=defl_pg,
        rim_contests_per_game=rim_cpg,
        rank=rank,
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


def _card_defense_zone(
    d_fg_pct, normal_fg_pct, pct_plusminus
) -> CardDefenseZone | None:
    if d_fg_pct is None and normal_fg_pct is None and pct_plusminus is None:
        return None
    return CardDefenseZone(
        d_fg_pct=d_fg_pct,
        normal_fg_pct=normal_fg_pct,
        pct_plusminus=pct_plusminus,
    )


# ---------------------------------------------------------------------------
# Service class
# ---------------------------------------------------------------------------


class PlayerCardService:
    """Orchestrates data fetching and computation for the player card."""

    def __init__(self, db: Session, player_id: int, season: str) -> None:
        self._db = db
        self._player_id = player_id
        self._season = season

    # ------------------------------------------------------------------
    # Public entry point
    # ------------------------------------------------------------------

    def build(self) -> PlayerCardData:
        """Fetch all data and build the complete PlayerCardData response."""
        player = self._get_player()

        # Core stat rows
        season_stat = self._first(SeasonStats)
        current_career = self._first(PlayerCareerStats)
        advanced = self._first(PlayerAdvancedStats)
        computed = self._first(PlayerComputedAdvanced)
        on_off = self._first(PlayerOnOffStats)
        impact_ctx = self._first(ContextualizedImpact)
        play_types = self._first(SeasonPlayTypeStats)
        shot_zones = self._all(PlayerShotZones)
        defense = self._first(PlayerDefensiveStats)
        career_rows = (
            self._db.query(PlayerCareerStats)
            .filter(PlayerCareerStats.player_id == self._player_id)
            .order_by(PlayerCareerStats.season)
            .all()
        )

        gp = (
            (current_career.games_played if current_career else None)
            or (season_stat.games_played if season_stat else None)
            or 1
        )

        # Build card sections
        traditional = self._build_traditional(current_career, season_stat, gp)
        advanced_stats = self._build_advanced(advanced, computed)
        radar = self._build_radar(computed)
        card_impact = self._build_impact(on_off, impact_ctx, player)
        card_play_types = self._build_play_types(play_types)
        card_shot_zones = self._build_shot_zones(shot_zones, gp)
        defensive_rank = self._compute_defensive_rank()
        card_defensive = self._build_defensive(
            defense, season_stat, gp, defensive_rank
        )
        card_career = self._build_career(career_rows, player)

        # Additional data models
        all_in_one_row = self._first(PlayerAllInOneMetrics)
        card_all_in_one = self._build_all_in_one(all_in_one_row)

        matchup_rows = (
            self._db.query(PlayerMatchups)
            .filter(
                PlayerMatchups.player_id == self._player_id,
                PlayerMatchups.season == self._season,
            )
            .order_by(PlayerMatchups.partial_poss.desc())
            .limit(5)
            .all()
        )
        card_matchups = self._build_matchups(matchup_rows)

        # Extra models for computed metrics
        shooting_tracking = self._first(PlayerShootingTracking)
        clutch_stats = self._first(PlayerClutchStats)
        per75 = (
            self._db.query(Per75Stats)
            .filter(Per75Stats.season == self._season)
            .join(SeasonStats, SeasonStats.id == Per75Stats.season_stats_id)
            .filter(SeasonStats.player_id == self._player_id)
            .first()
        )

        # Computed metrics
        card_scheme_scores, scheme_dict = self._compute_scheme_compatibility(
            play_types, advanced, per75, shooting_tracking, shot_zones
        )
        card_portability, portability_score = self._compute_portability(
            season_stat,
            play_types,
            shooting_tracking,
            advanced,
            on_off,
            per75,
            scheme_dict,
            card_scheme_scores,
        )
        card_championship = self._compute_championship(
            season_stat,
            advanced,
            play_types,
            clutch_stats,
            on_off,
            computed,
            all_in_one_row,
            career_rows,
            portability_score,
            gp,
        )
        card_luck = self._compute_luck_adjusted(
            on_off, season_stat, clutch_stats, advanced, player
        )
        card_opponent_tiers = self._compute_opponent_tiers(matchup_rows)
        card_lineup_ctx = self._build_lineup_context(on_off)

        # Tracking data sections
        card_speed_distance = self._build_speed_distance()
        card_passing = self._build_passing()
        card_reb_tracking = self._build_rebounding_tracking()
        card_def_dist = self._build_defender_distance()
        card_touches_breakdown = self._build_touches_breakdown()
        card_opponent_shooting = self._build_opponent_shooting()
        card_def_play_types = self._build_defensive_play_types()
        card_recent_games, card_consistency = self._build_games_and_consistency()

        # Derived "advanced signals" — composite stats built from the
        # existing data sections above. These read no new DB tables; they
        # synthesize sections already fetched (defender distance, play
        # types, passing, touches, on/off).
        card_friction = self._build_friction_efficiency()
        card_gravity = self._build_gravity_index(on_off)
        card_shot_diet = self._build_shot_diet(play_types)
        card_rim_gravity = self._build_rim_gravity(shot_zones)
        card_pass_funnel = self._build_pass_funnel(current_career, season_stat, gp)
        card_leverage_ts = self._build_leverage_ts()
        card_possession_dwell = self._build_possession_dwell(season_stat, gp)
        card_mile_production = self._build_mile_production(current_career, gp)
        card_late_trend = self._build_late_season_trend()
        card_def_terrain = self._build_defensive_terrain(defense)
        card_contest_conv = self._build_contest_conversion(season_stat, defense, gp)
        card_lineup_buoyancy = self._build_lineup_buoyancy()
        card_scheme_robustness = self._build_scheme_robustness(play_types)

        return PlayerCardData(
            id=player.id,
            nba_id=player.nba_id,
            name=player.name,
            position=player.position,
            team_abbreviation=player.team_abbreviation,
            height=player.height,
            weight=player.weight,
            jersey_number=player.jersey_number,
            age=player.birth_date,
            country=player.country,
            draft_year=player.draft_year,
            draft_round=player.draft_round,
            draft_number=player.draft_number,
            season=self._season,
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
            speed_distance=card_speed_distance,
            passing=card_passing,
            rebounding_tracking=card_reb_tracking,
            defender_distance=card_def_dist,
            touches_breakdown=card_touches_breakdown,
            opponent_shooting=card_opponent_shooting,
            defensive_play_types=card_def_play_types,
            recent_games=card_recent_games,
            consistency=card_consistency,
            friction_efficiency=card_friction,
            gravity_index=card_gravity,
            shot_diet=card_shot_diet,
            rim_gravity=card_rim_gravity,
            pass_funnel=card_pass_funnel,
            leverage_ts=card_leverage_ts,
            possession_dwell=card_possession_dwell,
            mile_production=card_mile_production,
            late_season_trend=card_late_trend,
            defensive_terrain=card_def_terrain,
            contest_conversion=card_contest_conv,
            lineup_buoyancy=card_lineup_buoyancy,
            scheme_robustness=card_scheme_robustness,
        )

    # ------------------------------------------------------------------
    # Query helpers
    # ------------------------------------------------------------------

    def _get_player(self) -> Player:
        player = (
            self._db.query(Player).filter(Player.id == self._player_id).first()
        )
        if not player:
            from fastapi import HTTPException

            raise HTTPException(status_code=404, detail="Player not found")
        return player

    def _first(self, model):
        """Fetch the first row matching player_id and season."""
        return (
            self._db.query(model)
            .filter(model.player_id == self._player_id, model.season == self._season)
            .first()
        )

    def _all(self, model):
        """Fetch all rows matching player_id and season."""
        return (
            self._db.query(model)
            .filter(model.player_id == self._player_id, model.season == self._season)
            .all()
        )

    # ------------------------------------------------------------------
    # Section builders
    # ------------------------------------------------------------------

    @staticmethod
    def _build_traditional(
        current_career: PlayerCareerStats | None,
        season_stat: SeasonStats | None,
        gp: int,
    ) -> CardTraditional | None:
        if not current_career and not season_stat:
            return None
        tov = None
        if season_stat and season_stat.total_turnovers:
            tov = Decimal(str(round(season_stat.total_turnovers / gp, 1)))
        return CardTraditional(
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

    @staticmethod
    def _build_advanced(
        advanced: PlayerAdvancedStats | None,
        computed: PlayerComputedAdvanced | None,
    ) -> CardAdvanced | None:
        if not advanced and not computed:
            return None
        return CardAdvanced(
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

    @staticmethod
    def _build_radar(computed: PlayerComputedAdvanced | None) -> CardRadar | None:
        if not computed:
            return None
        return CardRadar(
            scoring=computed.radar_scoring,
            playmaking=computed.radar_playmaking,
            defense=computed.radar_defense,
            efficiency=computed.radar_efficiency,
            volume=computed.radar_volume,
            durability=computed.radar_durability,
            clutch=computed.radar_clutch,
            versatility=computed.radar_versatility,
        )

    def _build_impact(
        self,
        on_off: PlayerOnOffStats | None,
        impact_ctx: ContextualizedImpact | None,
        player: Player,
    ) -> CardImpact | None:
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
            adjustments = []
            cumulative = safe_float(impact_ctx.raw_net_rating_diff)
            adjustments.append(
                CardAdjustmentStep(
                    name="Raw On/Off Net Rtg",
                    value=impact_ctx.raw_net_rating_diff,
                    cumulative=to_decimal(cumulative),
                    explanation="Baseline team net rating differential when player is on vs off court",
                )
            )
            tm_adj = safe_float(impact_ctx.teammate_adjustment)
            if tm_adj != 0:
                cumulative -= tm_adj
                adjustments.append(
                    CardAdjustmentStep(
                        name="Teammate Quality",
                        value=to_decimal(-tm_adj),
                        cumulative=to_decimal(cumulative),
                        explanation=f"Avg teammate net rating: {impact_ctx.avg_teammate_net_rating}",
                    )
                )
            opp_factor = safe_float(impact_ctx.opponent_quality_factor)
            if opp_factor != 0 and opp_factor != 1.0:
                old_cum = cumulative
                cumulative = cumulative * opp_factor
                adjustments.append(
                    CardAdjustmentStep(
                        name="Opponent Quality",
                        value=to_decimal(cumulative - old_cum),
                        cumulative=to_decimal(cumulative),
                        explanation=f"Pct minutes vs starters: {impact_ctx.pct_minutes_vs_starters}",
                    )
                )
            rel = safe_float(impact_ctx.reliability_factor)
            if rel != 0 and rel != 1.0:
                old_cum = cumulative
                cumulative = cumulative * rel
                adjustments.append(
                    CardAdjustmentStep(
                        name="Reliability",
                        value=to_decimal(cumulative - old_cum),
                        cumulative=to_decimal(cumulative),
                        explanation=f"Minutes: {impact_ctx.total_on_court_minutes}, factor: {impact_ctx.reliability_factor}",
                    )
                )

            ctx_data = CardContextualized(
                raw_net_rtg=impact_ctx.raw_net_rating_diff,
                contextualized_net_rtg=impact_ctx.contextualized_net_impact,
                percentile=impact_ctx.impact_percentile,
                adjustments=adjustments,
            )

        actual_wins = None
        if player.team_abbreviation:
            team_records = redis_cache.get(f"team_records:{self._season}")
            if team_records and player.team_abbreviation in team_records:
                actual_wins = team_records[player.team_abbreviation].get("wins")

        if on_off_data or ctx_data:
            return CardImpact(
                on_off=on_off_data, contextualized=ctx_data, actual_wins=actual_wins
            )
        return None

    @staticmethod
    def _build_play_types(
        play_types: SeasonPlayTypeStats | None,
    ) -> CardPlayTypes | None:
        if not play_types:
            return None
        return CardPlayTypes(
            isolation=_card_play_type(play_types, "isolation"),
            pnr_ball_handler=_card_play_type(play_types, "pnr_ball_handler"),
            pnr_roll_man=_card_play_type(play_types, "pnr_roll_man"),
            post_up=_card_play_type(play_types, "post_up"),
            spot_up=_card_play_type(play_types, "spot_up"),
            transition=_card_play_type(play_types, "transition"),
            cut=_card_play_type(play_types, "cut"),
            off_screen=_card_play_type(play_types, "off_screen"),
            handoff=_card_play_type(play_types, "handoff"),
        )

    @staticmethod
    def _build_shot_zones(
        shot_zones: list[PlayerShotZones], gp: int
    ) -> list[CardShotZone]:
        return [
            CardShotZone(
                zone=sz.zone,
                fga_per_game=(
                    Decimal(str(round(sz.fga / gp, 1))) if sz.fga else None
                ),
                fg_pct=sz.fg_pct,
                freq=sz.freq,
                league_avg=sz.league_avg,
            )
            for sz in shot_zones
        ]

    @staticmethod
    def _build_defensive(
        defense: PlayerDefensiveStats | None,
        season_stat: SeasonStats | None,
        gp: int,
        defensive_rank: int | None = None,
    ) -> CardDefensive | None:
        if not defense:
            return None
        return CardDefensive(
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
            iso_defense=(
                CardIsoDefense(
                    poss=defense.iso_poss,
                    ppp=defense.iso_ppp,
                    fg_pct=defense.iso_fg_pct,
                    percentile=defense.iso_percentile,
                )
                if defense.iso_poss
                else None
            ),
            overview=_build_defense_overview(
                season_stat, defense, gp, defensive_rank
            ),
        )

    def _compute_defensive_rank(self) -> int | None:
        """Compute this player's league rank by rapm_defense for the season.

        Qualifying set: players with non-null rapm_defense and >= 500 total
        season minutes (via SeasonStats.total_minutes — same minutes source
        used elsewhere in this service for season aggregates). Ranks are
        1-indexed, descending by rapm_defense. Returns None if the player
        isn't in the qualifying set.
        """
        qualifying_minutes = 500
        rows = (
            self._db.query(
                PlayerAllInOneMetrics.player_id,
                PlayerAllInOneMetrics.rapm_defense,
            )
            .join(
                SeasonStats,
                (SeasonStats.player_id == PlayerAllInOneMetrics.player_id)
                & (SeasonStats.season == PlayerAllInOneMetrics.season),
            )
            .filter(
                PlayerAllInOneMetrics.season == self._season,
                PlayerAllInOneMetrics.rapm_defense.isnot(None),
                SeasonStats.total_minutes.isnot(None),
                SeasonStats.total_minutes >= qualifying_minutes,
            )
            .order_by(PlayerAllInOneMetrics.rapm_defense.desc())
            .all()
        )
        for idx, row in enumerate(rows, start=1):
            if row.player_id == self._player_id:
                return idx
        return None

    def _build_career(
        self, career_rows: list[PlayerCareerStats], player: Player
    ) -> list[CardCareerSeason]:
        computed_by_season = {
            row.season: row
            for row in self._db.query(PlayerComputedAdvanced)
            .filter(PlayerComputedAdvanced.player_id == self._player_id)
            .all()
        }

        # Load DARKO DPM history keyed by integer season year (e.g. "2022-23" -> 2023).
        # DarkoHistory is keyed by nba_id (NBA's canonical player id), not our internal
        # player_id, so we join via Player.nba_id.
        darko_by_year: dict[int, Decimal] = {}
        if player.nba_id is not None:
            for row in (
                self._db.query(DarkoHistory)
                .filter(DarkoHistory.nba_id == player.nba_id)
                .all()
            ):
                if row.season is not None and row.dpm is not None:
                    darko_by_year[row.season] = row.dpm

        def _season_to_year(season_str: str) -> int | None:
            # "2022-23" -> 2023; safe-guard against unexpected formats.
            try:
                return int(season_str.split("-")[0]) + 1
            except (ValueError, IndexError, AttributeError):
                return None

        return [
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
                per=(
                    computed_by_season[row.season].per
                    if row.season in computed_by_season
                    else None
                ),
                ws48=(
                    computed_by_season[row.season].ws_per_48
                    if row.season in computed_by_season
                    else None
                ),
                bpm=(
                    computed_by_season[row.season].bpm
                    if row.season in computed_by_season
                    else None
                ),
                epm=darko_by_year.get(_season_to_year(row.season) or -1),
            )
            for row in career_rows
        ]

    @staticmethod
    def _build_all_in_one(
        all_in_one_row: PlayerAllInOneMetrics | None,
    ) -> CardAllInOne | None:
        if not all_in_one_row:
            return None
        return CardAllInOne(
            rapm=all_in_one_row.rapm,
            rapm_offense=all_in_one_row.rapm_offense,
            rapm_defense=all_in_one_row.rapm_defense,
            rpm=all_in_one_row.rpm,
            rpm_offense=all_in_one_row.rpm_offense,
            rpm_defense=all_in_one_row.rpm_defense,
            epm=all_in_one_row.epm,
            epm_offense=all_in_one_row.epm_offense,
            epm_defense=all_in_one_row.epm_defense,
            lebron=all_in_one_row.lebron,
            lebron_offense=all_in_one_row.lebron_offense,
            lebron_defense=all_in_one_row.lebron_defense,
            darko=all_in_one_row.darko,
            darko_offense=all_in_one_row.darko_offense,
            darko_defense=all_in_one_row.darko_defense,
            laker=all_in_one_row.laker,
            laker_offense=all_in_one_row.laker_offense,
            laker_defense=all_in_one_row.laker_defense,
            mamba=all_in_one_row.mamba,
            mamba_offense=all_in_one_row.mamba_offense,
            mamba_defense=all_in_one_row.mamba_defense,
        )

    @staticmethod
    def _build_matchups(matchup_rows: list[PlayerMatchups]) -> list[CardMatchup]:
        return [
            CardMatchup(
                opponent=m.off_player_name,
                possessions=m.partial_poss,
                dfg_pct=m.matchup_fg_pct,
                pts_allowed=m.player_pts,
            )
            for m in matchup_rows
        ]

    # ------------------------------------------------------------------
    # Computed metrics
    # ------------------------------------------------------------------

    def _compute_scheme_compatibility(
        self,
        play_types,
        advanced,
        per75,
        shooting_tracking,
        shot_zones,
    ) -> tuple[list[CardSchemeScore], dict | None]:
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
        return card_scheme_scores, scheme_dict

    def _compute_portability(
        self,
        season_stat,
        play_types,
        shooting_tracking,
        advanced,
        on_off,
        per75,
        scheme_dict,
        card_scheme_scores,
    ) -> tuple[CardPortability | None, float]:
        portability_score = 50.0
        if not (season_stat and play_types and advanced):
            return None, portability_score

        all_matchups = (
            self._db.query(PlayerMatchups)
            .filter(
                PlayerMatchups.player_id == self._player_id,
                PlayerMatchups.season == self._season,
            )
            .all()
        )
        all_player_positions = {
            p.nba_id: p.position
            for p in self._db.query(Player.nba_id, Player.position).all()
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

        teammate_dependency = self._build_teammate_dependency()

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
            teammate_dependency=teammate_dependency,
        )
        return card_portability, portability_score

    # ------------------------------------------------------------------
    # Teammate dependency (on-court net rating by lineup context)
    # ------------------------------------------------------------------

    # Minimum total minutes in a bucket before we report its NRtg. Below
    # this threshold the sample is too small to separate signal from noise
    # (a 20-min sample can easily show +30 or -30 NRtg at random).
    _TEAMMATE_DEP_MIN_MINUTES = Decimal("50")

    # Season-level qualifying thresholds for classifying teammates.
    _ELITE_SPACER_FG3_PCT = Decimal("0.38")
    _ELITE_SPACER_FG3A = 100  # season 3PA floor
    _RIM_PROTECTOR_PCT_PLUSMINUS = Decimal("-0.03")
    _RIM_PROTECTOR_D_FGA = Decimal("200")  # rim FGAs defended floor

    def _load_elite_spacer_ids(self) -> set[int]:
        """Return the set of player ids that qualify as elite spacers this season.

        Qualifying set: players whose season fg3_pct >= 0.38 AND fg3a >= 100.
        Computed as a single bulk query against SeasonStats.
        """
        rows = (
            self._db.query(
                SeasonStats.player_id,
                SeasonStats.total_fg3m,
                SeasonStats.total_fg3a,
            )
            .filter(
                SeasonStats.season == self._season,
                SeasonStats.total_fg3a.isnot(None),
                SeasonStats.total_fg3a >= self._ELITE_SPACER_FG3A,
            )
            .all()
        )
        ids: set[int] = set()
        for row in rows:
            fg3a = row.total_fg3a or 0
            fg3m = row.total_fg3m or 0
            if fg3a <= 0:
                continue
            if Decimal(fg3m) / Decimal(fg3a) >= self._ELITE_SPACER_FG3_PCT:
                ids.add(row.player_id)
        return ids

    def _load_rim_protector_ids(self) -> set[int]:
        """Return the set of player ids that qualify as rim protectors this season.

        Qualifying set: players with rim_pct_plusminus <= -0.03 (at least 3pp
        better than the league average at the rim; negative is good) AND
        rim_d_fga >= 200 (enough rim shots defended to trust the signal).
        """
        rows = (
            self._db.query(PlayerDefensiveStats.player_id)
            .filter(
                PlayerDefensiveStats.season == self._season,
                PlayerDefensiveStats.rim_pct_plusminus.isnot(None),
                PlayerDefensiveStats.rim_pct_plusminus
                <= self._RIM_PROTECTOR_PCT_PLUSMINUS,
                PlayerDefensiveStats.rim_d_fga.isnot(None),
                PlayerDefensiveStats.rim_d_fga >= self._RIM_PROTECTOR_D_FGA,
            )
            .all()
        )
        return {row.player_id for row in rows}

    def _build_teammate_dependency(self) -> CardTeammateDependency | None:
        """Aggregate the player's on-court net rating by teammate context.

        Pulls every lineup_stats row for (player, season), classifies each
        row by counting qualifying teammates (elite spacers / rim protectors)
        in the other four slots, and computes minutes-weighted average
        net_rating per bucket.

        Returns None if the player has no lineup data for the season.
        """
        lineups = (
            self._db.query(LineupStats)
            .filter(
                LineupStats.season == self._season,
                or_(
                    LineupStats.player1_id == self._player_id,
                    LineupStats.player2_id == self._player_id,
                    LineupStats.player3_id == self._player_id,
                    LineupStats.player4_id == self._player_id,
                    LineupStats.player5_id == self._player_id,
                ),
            )
            .all()
        )
        if not lineups:
            return None

        elite_spacer_ids = self._load_elite_spacer_ids()
        rim_protector_ids = self._load_rim_protector_ids()

        # Bucket accumulators: (sum(net * min), sum(min))
        zero = Decimal("0")
        buckets: dict[str, list[Decimal]] = {
            "elite_spacing": [zero, zero],
            "poor_spacing": [zero, zero],
            "with_rim": [zero, zero],
            "without_rim": [zero, zero],
        }

        for lu in lineups:
            minutes = lu.minutes
            net = lu.net_rating
            if minutes is None or net is None or minutes <= 0:
                continue

            teammates = [
                pid
                for pid in (
                    lu.player1_id,
                    lu.player2_id,
                    lu.player3_id,
                    lu.player4_id,
                    lu.player5_id,
                )
                if pid != self._player_id
            ]
            spacer_count = sum(1 for pid in teammates if pid in elite_spacer_ids)
            rim_count = sum(1 for pid in teammates if pid in rim_protector_ids)

            contribution = net * minutes
            if spacer_count >= 2:
                buckets["elite_spacing"][0] += contribution
                buckets["elite_spacing"][1] += minutes
            if spacer_count == 0:
                buckets["poor_spacing"][0] += contribution
                buckets["poor_spacing"][1] += minutes
            if rim_count >= 1:
                buckets["with_rim"][0] += contribution
                buckets["with_rim"][1] += minutes
            else:
                buckets["without_rim"][0] += contribution
                buckets["without_rim"][1] += minutes

        def _avg(bucket_key: str) -> tuple[Decimal | None, Decimal | None]:
            weighted, total_min = buckets[bucket_key]
            if total_min < self._TEAMMATE_DEP_MIN_MINUTES:
                # Not enough minutes to report an NRtg, but still surface the
                # minutes so the UI can explain why it's "N/A".
                minutes_out = total_min if total_min > 0 else None
                return None, minutes_out
            net = (weighted / total_min).quantize(Decimal("0.01"))
            return net, total_min.quantize(Decimal("0.01"))

        elite_net, elite_min = _avg("elite_spacing")
        poor_net, poor_min = _avg("poor_spacing")
        with_rim_net, with_rim_min = _avg("with_rim")
        without_rim_net, without_rim_min = _avg("without_rim")

        spacing_delta: Decimal | None = None
        if elite_net is not None and poor_net is not None:
            spacing_delta = (elite_net - poor_net).quantize(Decimal("0.01"))

        return CardTeammateDependency(
            elite_spacing_net_rtg=elite_net,
            elite_spacing_minutes=elite_min,
            poor_spacing_net_rtg=poor_net,
            poor_spacing_minutes=poor_min,
            spacing_delta=spacing_delta,
            with_rim_protector_net_rtg=with_rim_net,
            with_rim_protector_minutes=with_rim_min,
            without_rim_protector_net_rtg=without_rim_net,
            without_rim_protector_minutes=without_rim_min,
        )

    def _compute_championship(
        self,
        season_stat,
        advanced,
        play_types,
        clutch_stats,
        on_off,
        computed,
        all_in_one_row,
        career_rows,
        portability_score: float,
        gp: int,
    ) -> CardChampionship | None:
        if not (season_stat and advanced):
            return None

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

        reg_ppg = safe_float(season_stat.total_points) / max(1, gp)
        reg_ts = safe_float(advanced.ts_pct) if advanced else 0.55
        usg = safe_float(advanced.usg_pct, 0.20) if advanced else 0.20
        ts_drop = 0.010 if usg >= 0.28 else (0.018 if usg >= 0.22 else 0.028)
        proj_ts = reg_ts - ts_drop
        proj_ppg = (
            reg_ppg
            * ((usg + (0.02 if usg >= 0.25 else 0)) / max(0.01, usg))
            * (proj_ts / max(0.01, reg_ts))
        )

        # AST is fairly stable reg->playoffs; project straight through.
        reg_apg = safe_float(season_stat.total_assists) / max(1, gp)
        proj_apg = reg_apg

        # DRtg is historically stable reg->playoffs; pass-through (no model).
        reg_drtg = advanced.def_rating if advanced else None
        proj_drtg = reg_drtg

        playoff_proj = CardPlayoffProjection(
            projected_ppg=to_decimal(proj_ppg),
            projected_ts=to_decimal(proj_ts, "0.001"),
            reg_ppg=to_decimal(reg_ppg),
            reg_ts=to_decimal(reg_ts, "0.001"),
            projected_ast=to_decimal(proj_apg),
            reg_ast=to_decimal(reg_apg),
            projected_drtg=proj_drtg,
            reg_drtg=reg_drtg,
        )

        return CardChampionship(
            index=to_decimal(champ_result.championship_index),
            tier=champ_result.tier,
            win_probability=to_decimal(champ_result.win_probability, "0.0001"),
            multiplier_vs_base=to_decimal(champ_result.multiplier_vs_base),
            pillars=[
                CardChampionshipPillar(
                    name="Playoff Scoring",
                    score=to_decimal(champ_result.playoff_scoring),
                    weight=to_decimal(0.25),
                ),
                CardChampionshipPillar(
                    name="Two-Way Impact",
                    score=to_decimal(champ_result.two_way_impact),
                    weight=to_decimal(0.20),
                ),
                CardChampionshipPillar(
                    name="Clutch Performance",
                    score=to_decimal(champ_result.clutch_performance),
                    weight=to_decimal(0.15),
                ),
                CardChampionshipPillar(
                    name="Portability",
                    score=to_decimal(champ_result.portability),
                    weight=to_decimal(0.15),
                ),
                CardChampionshipPillar(
                    name="Durability",
                    score=to_decimal(champ_result.durability),
                    weight=to_decimal(0.10),
                ),
                CardChampionshipPillar(
                    name="Experience & Arc",
                    score=to_decimal(champ_result.experience_arc),
                    weight=to_decimal(0.10),
                ),
                CardChampionshipPillar(
                    name="Supporting Cast",
                    score=to_decimal(champ_result.supporting_cast),
                    weight=to_decimal(0.05),
                ),
            ],
            playoff_projection=playoff_proj,
        )

    def _compute_luck_adjusted(
        self, on_off, season_stat, clutch_stats, advanced, player
    ) -> CardLuckAdjusted | None:
        if not (on_off and season_stat and clutch_stats):
            return None

        team_season = (
            self._db.query(SeasonStats)
            .filter(SeasonStats.season == self._season)
            .join(Player, Player.id == SeasonStats.player_id)
            .filter(Player.team_abbreviation == player.team_abbreviation)
            .all()
        )
        team_pts = sum(safe_float(s.total_points) for s in team_season)
        team_gp = (
            max(1, max((s.games_played or 0) for s in team_season))
            if team_season
            else 82
        )

        league_pace = safe_float(advanced.pace) if advanced else 100.0

        luck_calc = LuckAdjustedCalculator()
        team_stats_dict = {
            "pts_for": team_pts / team_gp * 100,
            "pts_against": team_pts / team_gp * 100,
            "games": team_gp,
        }

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
        return CardLuckAdjusted(
            x_wins=to_decimal(luck_result["x_wins"]),
            clutch_epa=to_decimal(luck_result["clutch_epa"]),
            clutch_epa_per_game=to_decimal(luck_result["clutch_epa_per_game"]),
            garbage_time_ppg=to_decimal(luck_result["garbage_time_ppg"]),
        )

    def _compute_opponent_tiers(
        self, matchup_rows
    ) -> list[CardOpponentTierEntry]:
        if not matchup_rows:
            return []

        all_player_matchups = (
            self._db.query(PlayerMatchups)
            .filter(
                PlayerMatchups.player_id == self._player_id,
                PlayerMatchups.season == self._season,
            )
            .all()
        )

        all_aio = {
            row.player_id: row
            for row in self._db.query(PlayerAllInOneMetrics)
            .filter(PlayerAllInOneMetrics.season == self._season)
            .all()
        }
        all_comp = {
            row.player_id: row
            for row in self._db.query(PlayerComputedAdvanced)
            .filter(PlayerComputedAdvanced.season == self._season)
            .all()
        }
        all_ss = {
            row.player_id: row
            for row in self._db.query(SeasonStats)
            .filter(SeasonStats.season == self._season)
            .all()
        }

        tier_calc = OpponentTierCalculator()
        opponent_tiers = tier_calc.assign_tiers(all_aio, all_comp, all_ss)
        tier_perf = tier_calc.performance_by_tier(
            self._player_id, all_player_matchups, opponent_tiers
        )

        result: list[CardOpponentTierEntry] = []
        for tier_name in ["Elite", "Quality", "Role", "Bench"]:
            data = tier_perf.get(tier_name)
            if data:
                result.append(
                    CardOpponentTierEntry(
                        tier=tier_name,
                        possessions=data["possessions"],
                        dfg_pct=to_decimal(data["dfg_pct"], "0.001"),
                        ppp_allowed=to_decimal(data["ppp_allowed"], "0.001"),
                        weight=to_decimal(TIER_WEIGHTS[tier_name]),
                    )
                )
        return result

    def _build_lineup_context(
        self, on_off: PlayerOnOffStats | None
    ) -> CardLineupContext | None:
        player_lineups = (
            self._db.query(LineupStats)
            .filter(
                LineupStats.season == self._season,
                or_(
                    LineupStats.player1_id == self._player_id,
                    LineupStats.player2_id == self._player_id,
                    LineupStats.player3_id == self._player_id,
                    LineupStats.player4_id == self._player_id,
                    LineupStats.player5_id == self._player_id,
                ),
            )
            .order_by(LineupStats.minutes.desc())
            .limit(3)
            .all()
        )

        if not player_lineups:
            return None

        lineup_player_ids: set[int] = set()
        for lu in player_lineups:
            lineup_player_ids.update(
                [lu.player1_id, lu.player2_id, lu.player3_id, lu.player4_id, lu.player5_id]
            )
        id_to_name: dict[int, str] = {
            p.id: p.name
            for p in self._db.query(Player.id, Player.name)
            .filter(Player.id.in_(lineup_player_ids))
            .all()
        }

        team_baseline = Decimal("0")
        if on_off and on_off.on_court_net_rating is not None:
            team_baseline = on_off.on_court_net_rating

        full_reliability_minutes = Decimal("200")

        def _lineup_ctx_net(raw_net: Decimal | None, minutes: Decimal | None) -> Decimal:
            if raw_net is None:
                return team_baseline
            mins = minutes or Decimal("0")
            ratio = mins / full_reliability_minutes
            reliability = min(
                Decimal("1"),
                ratio.sqrt() if hasattr(ratio, "sqrt") else Decimal(str(float(ratio) ** 0.5)),
            )
            return (
                raw_net * reliability + team_baseline * (Decimal("1") - reliability)
            ).quantize(Decimal("0.01"))

        def _opp_tier(net: Decimal | None) -> str:
            if net is None:
                return ""
            v = float(net)
            if v >= 5:
                return "Elite"
            if v >= 0:
                return "Good"
            if v >= -5:
                return "Average"
            return "Poor"

        top_lineups = []
        for lu in player_lineups:
            slot_ids = [
                lu.player1_id, lu.player2_id, lu.player3_id,
                lu.player4_id, lu.player5_id,
            ]
            names = [id_to_name.get(pid, "?") for pid in slot_ids]
            top_lineups.append(
                CardLineup(
                    players=names,
                    minutes=lu.minutes,
                    raw_net=lu.net_rating,
                    ctx_net=_lineup_ctx_net(lu.net_rating, lu.minutes),
                    opp_tier=_opp_tier(lu.net_rating),
                )
            )

        without_top_tm = self._build_without_top_teammate(on_off, id_to_name)

        return CardLineupContext(
            top_lineups=top_lineups,
            without_top_teammate=without_top_tm,
        )

    def _build_without_top_teammate(
        self,
        on_off: PlayerOnOffStats | None,
        id_to_name: dict[int, str],
    ) -> CardWithoutTeammate | None:
        if not on_off:
            return None

        teammate_minutes: dict[int, Decimal] = {}
        all_player_lineups = (
            self._db.query(LineupStats)
            .filter(
                LineupStats.season == self._season,
                or_(
                    LineupStats.player1_id == self._player_id,
                    LineupStats.player2_id == self._player_id,
                    LineupStats.player3_id == self._player_id,
                    LineupStats.player4_id == self._player_id,
                    LineupStats.player5_id == self._player_id,
                ),
            )
            .all()
        )
        for lu in all_player_lineups:
            slot_ids = [
                lu.player1_id, lu.player2_id, lu.player3_id,
                lu.player4_id, lu.player5_id,
            ]
            lu_min = lu.minutes or Decimal("0")
            for pid in slot_ids:
                if pid != self._player_id:
                    teammate_minutes[pid] = teammate_minutes.get(pid, Decimal("0")) + lu_min

        if not teammate_minutes:
            return None

        top_tm_id = max(teammate_minutes, key=lambda k: teammate_minutes[k])
        top_tm_name = id_to_name.get(top_tm_id) or (
            self._db.query(Player.name).filter(Player.id == top_tm_id).scalar()
        ) or "?"

        tm_on_off = (
            self._db.query(PlayerOnOffStats)
            .filter(
                PlayerOnOffStats.player_id == top_tm_id,
                PlayerOnOffStats.season == self._season,
            )
            .first()
        )
        if tm_on_off:
            return CardWithoutTeammate(
                teammate=top_tm_name,
                net_rtg=tm_on_off.off_court_net_rating,
                minutes=tm_on_off.off_court_minutes,
            )
        return None

    # ------------------------------------------------------------------
    # Tracking data sections
    # ------------------------------------------------------------------

    def _build_speed_distance(self) -> CardSpeedDistance | None:
        sd_row = self._first(PlayerSpeedDistance)
        if not sd_row:
            return None
        return CardSpeedDistance(
            dist_miles=sd_row.dist_miles,
            dist_miles_off=sd_row.dist_miles_off,
            dist_miles_def=sd_row.dist_miles_def,
            avg_speed=sd_row.avg_speed,
            avg_speed_off=sd_row.avg_speed_off,
            avg_speed_def=sd_row.avg_speed_def,
        )

    def _build_passing(self) -> CardPassing | None:
        pass_row = self._first(PlayerPassingStats)
        if not pass_row:
            return None
        return CardPassing(
            passes_made=pass_row.passes_made,
            passes_received=pass_row.passes_received,
            secondary_ast=pass_row.secondary_ast,
            potential_ast=pass_row.potential_ast,
            ast_points_created=pass_row.ast_points_created,
            ast_adj=pass_row.ast_adj,
            ast_to_pass_pct=pass_row.ast_to_pass_pct,
            ast_to_pass_pct_adj=pass_row.ast_to_pass_pct_adj,
        )

    def _build_rebounding_tracking(self) -> CardReboundingTracking | None:
        reb_row = self._first(PlayerReboundingTracking)
        if not reb_row:
            return None
        return CardReboundingTracking(
            oreb_contest_pct=reb_row.oreb_contest_pct,
            oreb_chance_pct=reb_row.oreb_chance_pct,
            oreb_chance_pct_adj=reb_row.oreb_chance_pct_adj,
            avg_oreb_dist=reb_row.avg_oreb_dist,
            dreb_contest_pct=reb_row.dreb_contest_pct,
            dreb_chance_pct=reb_row.dreb_chance_pct,
            dreb_chance_pct_adj=reb_row.dreb_chance_pct_adj,
            avg_dreb_dist=reb_row.avg_dreb_dist,
            reb_contest_pct=reb_row.reb_contest_pct,
            reb_chance_pct=reb_row.reb_chance_pct,
            reb_chance_pct_adj=reb_row.reb_chance_pct_adj,
        )

    def _build_touches_breakdown(self) -> CardTouchesBreakdown | None:
        tb_row = self._first(PlayerTouchesBreakdown)
        if not tb_row:
            return None

        def _kind(internal_prefix: str, touches_attr: str) -> CardTouchKind | None:
            touches = getattr(tb_row, touches_attr)
            if not touches:
                return None
            return CardTouchKind(
                touches=touches,
                fga=getattr(tb_row, f"{internal_prefix}_fga"),
                fg_pct=getattr(tb_row, f"{internal_prefix}_fg_pct"),
                fta=getattr(tb_row, f"{internal_prefix}_fta"),
                pts=getattr(tb_row, f"{internal_prefix}_pts"),
                passes=getattr(tb_row, f"{internal_prefix}_passes"),
                ast=getattr(tb_row, f"{internal_prefix}_ast"),
                tov=getattr(tb_row, f"{internal_prefix}_tov"),
                fouls=getattr(tb_row, f"{internal_prefix}_fouls"),
                pts_per_touch=getattr(tb_row, f"{internal_prefix}_pts_per_touch"),
            )

        elbow = _kind("elbow_touch", "elbow_touches")
        post = _kind("post_touch", "post_touches")
        paint = _kind("paint_touch", "paint_touches")
        if not any((elbow, post, paint)):
            return None
        return CardTouchesBreakdown(elbow=elbow, post=post, paint=paint)

    def _build_opponent_shooting(self) -> CardOpponentShooting | None:
        opp_row = self._first(PlayerOpponentShooting)
        if not opp_row:
            return None
        buckets: list[CardOpponentShootingBucket] = []
        for prefix, label in (
            ("lt_10ft", "< 10 ft"),
            ("two_pt", "All 2PT"),
            ("long_mid", "> 15 ft (2PT)"),
        ):
            fga = getattr(opp_row, f"{prefix}_defended_fga")
            if not fga:
                continue
            buckets.append(
                CardOpponentShootingBucket(
                    label=label,
                    defended_fga=fga,
                    defended_fg_pct=getattr(opp_row, f"{prefix}_defended_fg_pct"),
                    normal_fg_pct=getattr(opp_row, f"{prefix}_normal_fg_pct"),
                    pct_plusminus=getattr(opp_row, f"{prefix}_pct_plusminus"),
                )
            )
        if not buckets:
            return None
        return CardOpponentShooting(games=opp_row.two_pt_games, buckets=buckets)

    def _build_defender_distance(self) -> list[CardDefenderDistanceEntry]:
        dd_row = self._first(PlayerDefenderDistanceShooting)
        if not dd_row:
            return []
        result: list[CardDefenderDistanceEntry] = []
        for prefix, label in [
            ("very_tight", "0-2 ft"),
            ("tight", "2-4 ft"),
            ("open", "4-6 ft"),
            ("wide_open", "6+ ft"),
        ]:
            result.append(
                CardDefenderDistanceEntry(
                    range=label,
                    fga_freq=getattr(dd_row, f"{prefix}_fga_freq"),
                    fg_pct=getattr(dd_row, f"{prefix}_fg_pct"),
                    efg_pct=getattr(dd_row, f"{prefix}_efg_pct"),
                    fg3_pct=getattr(dd_row, f"{prefix}_fg3_pct"),
                )
            )
        return result

    def _build_defensive_play_types(self) -> CardDefensivePlayTypes | None:
        dpt_row = self._first(PlayerDefensivePlayTypes)
        if not dpt_row:
            return None

        def _card_def_pt(prefix: str) -> CardDefensivePlayType | None:
            poss = getattr(dpt_row, f"{prefix}_poss")
            if not poss:
                return None
            return CardDefensivePlayType(
                poss=poss,
                ppp=getattr(dpt_row, f"{prefix}_ppp"),
                fg_pct=getattr(dpt_row, f"{prefix}_fg_pct"),
                tov_pct=getattr(dpt_row, f"{prefix}_tov_pct"),
                freq=getattr(dpt_row, f"{prefix}_freq"),
                percentile=getattr(dpt_row, f"{prefix}_percentile"),
            )

        return CardDefensivePlayTypes(
            isolation=_card_def_pt("iso"),
            pnr_ball_handler=_card_def_pt("pnr_ball_handler"),
            post_up=_card_def_pt("post_up"),
            spot_up=_card_def_pt("spot_up"),
            transition=_card_def_pt("transition"),
        )

    def _build_games_and_consistency(
        self,
    ) -> tuple[list[CardGameLog], CardConsistency | None]:
        recent_game_rows = (
            self._db.query(GameStats)
            .filter(
                GameStats.player_id == self._player_id,
                GameStats.season == self._season,
            )
            .order_by(GameStats.game_date.desc())
            .limit(10)
            .all()
        )
        card_recent_games = [
            CardGameLog(
                game_date=g.game_date,
                matchup=g.matchup,
                wl=g.wl,
                minutes=g.minutes,
                pts=g.points,
                reb=g.rebounds,
                ast=g.assists,
                stl=g.steals,
                blk=g.blocks,
                tov=g.turnovers,
                fg_pct=g.fg_pct,
                fg3_pct=g.fg3_pct,
                plus_minus=g.plus_minus,
                game_score=g.game_score,
            )
            for g in recent_game_rows
        ]

        card_consistency = None
        cons_row = self._first(PlayerConsistencyStats)
        if cons_row:
            card_consistency = CardConsistency(
                games_used=cons_row.games_used,
                pts_cv=cons_row.pts_cv,
                ast_cv=cons_row.ast_cv,
                reb_cv=cons_row.reb_cv,
                game_score_cv=cons_row.game_score_cv,
                game_score_avg=cons_row.game_score_avg,
                game_score_std=cons_row.game_score_std,
                game_score_max=cons_row.game_score_max,
                game_score_min=cons_row.game_score_min,
                boom_games=cons_row.boom_games,
                bust_games=cons_row.bust_games,
                boom_pct=cons_row.boom_pct,
                bust_pct=cons_row.bust_pct,
                best_streak=cons_row.best_streak,
                worst_streak=cons_row.worst_streak,
                dd_rate=cons_row.dd_rate,
                td_rate=cons_row.td_rate,
                consistency_score=cons_row.consistency_score,
            )

        return card_recent_games, card_consistency

    # ------------------------------------------------------------------
    # Derived "advanced signal" metrics
    # ------------------------------------------------------------------

    # League-average rim FG% used as the zero point for rim_fg_pct_vs_league.
    # Restricted-area league avg hovers around .640 in recent seasons — using
    # a fixed baseline keeps the metric interpretable without a league join.
    _LEAGUE_AVG_RIM_FG_PCT = 0.640

    def _build_friction_efficiency(self) -> CardFrictionEfficiency | None:
        """Shooting eFG% by defender distance + a single friction slope.

        Requires the full defender-distance row. Slope uses eFG% so 3s
        get their proper weight: a tight-contested 3 hurts efficiency
        more than a tight-contested 2, which is the signal we care about.
        """
        dd = self._first(PlayerDefenderDistanceShooting)
        if not dd:
            return None

        very_tight = dd.very_tight_efg_pct
        tight = dd.tight_efg_pct
        open_ = dd.open_efg_pct
        wide_open = dd.wide_open_efg_pct

        buckets = [very_tight, tight, open_, wide_open]
        present = [safe_float(b) for b in buckets if b is not None]
        if not present:
            return None

        slope = None
        if very_tight is not None and wide_open is not None:
            slope = to_decimal(
                safe_float(wide_open) - safe_float(very_tight), "0.001"
            )
        pressure_adj = to_decimal(sum(present) / len(present), "0.001")

        return CardFrictionEfficiency(
            very_tight_efg=very_tight,
            tight_efg=tight,
            open_efg=open_,
            wide_open_efg=wide_open,
            friction_slope=slope,
            pressure_adjusted_efg=pressure_adj,
        )

    def _build_gravity_index(
        self, on_off: PlayerOnOffStats | None
    ) -> CardGravityIndex | None:
        """Proxy gravity via tight-coverage share + team off-rating lift.

        Combines two signals that are both weakly correlated with true
        gravity (teammate CS3 defender-distance on/off isn't exposed by
        the NBA Stats endpoints we ingest):
        - tight_attention_rate: defenders assign tighter coverage to
          threats, so a high share of very-tight + tight FGA indicates
          the defense is respecting the player's gravity.
        - team_off_lift: when a gravity player exits, offense usually
          slips; positive lift is consistent with drawing attention.

        Weighted 60/40 toward the defender-proximity signal because it's
        a direct per-shot observation, where on/off is noisy at the
        season level.
        """
        dd = self._first(PlayerDefenderDistanceShooting)
        if not dd and not on_off:
            return None

        tight_attention = None
        if dd and (dd.very_tight_fga_freq is not None or dd.tight_fga_freq is not None):
            tight_attention = to_decimal(
                safe_float(dd.very_tight_fga_freq) + safe_float(dd.tight_fga_freq),
                "0.001",
            )

        team_lift = None
        if on_off and on_off.off_rating_diff is not None:
            team_lift = on_off.off_rating_diff

        # 0-100 composite. Clamps inputs before weighting.
        # tight_attention: league-wide leaders sit around 0.55; floor ~0.25.
        # team_lift: typical range -8 .. +12 pts/100 poss.
        tight_norm = 0.0
        if tight_attention is not None:
            tight_norm = max(0.0, min(1.0, (safe_float(tight_attention) - 0.25) / 0.30))
        lift_norm = 0.0
        if team_lift is not None:
            lift_norm = max(0.0, min(1.0, (safe_float(team_lift) + 8.0) / 20.0))

        if tight_attention is None and team_lift is None:
            return None
        # Weight absent signal to 0 and renormalize so one-sided data
        # still produces a score on the same 0-100 scale.
        weights = (
            0.6 if tight_attention is not None else 0.0,
            0.4 if team_lift is not None else 0.0,
        )
        total_w = weights[0] + weights[1]
        if total_w == 0:
            return None
        gravity = (
            100.0 * (tight_norm * weights[0] + lift_norm * weights[1]) / total_w
        )

        return CardGravityIndex(
            tight_attention_rate=tight_attention,
            team_off_lift=team_lift,
            gravity_index=to_decimal(gravity, "0.1"),
        )

    @staticmethod
    def _build_shot_diet(
        play_types: SeasonPlayTypeStats | None,
    ) -> CardShotDiet | None:
        """Shannon entropy over the player's offensive play-type mix.

        Uses NBA's `_freq` fields directly (they sum to ~1.0 across the
        nine tracked play types). Normalized entropy = entropy / log2(n)
        so values live on [0, 1] regardless of how many modes are
        populated for this player.
        """
        if not play_types:
            return None
        attrs = [
            ("isolation", "isolation_freq"),
            ("pnr_ball_handler", "pnr_ball_handler_freq"),
            ("pnr_roll_man", "pnr_roll_man_freq"),
            ("post_up", "post_up_freq"),
            ("spot_up", "spot_up_freq"),
            ("transition", "transition_freq"),
            ("cut", "cut_freq"),
            ("off_screen", "off_screen_freq"),
            ("handoff", "handoff_freq"),
        ]
        freq_pairs: list[tuple[str, float]] = []
        for name, attr in attrs:
            v = safe_float(getattr(play_types, attr, None))
            if v > 0:
                freq_pairs.append((name, v))
        if not freq_pairs:
            return None

        # Renormalize in case NBA's freqs drift from 1.0 due to rounding.
        total = sum(v for _, v in freq_pairs)
        if total <= 0:
            return None
        probs = [(name, v / total) for name, v in freq_pairs]

        entropy = -sum(p * math.log2(p) for _, p in probs if p > 0)
        n = len(probs)
        max_entropy = math.log2(n) if n > 1 else 1.0
        entropy_norm = entropy / max_entropy if max_entropy > 0 else 0.0

        primary_modes = sum(1 for _, p in probs if p >= 0.10)
        top_name, top_p = max(probs, key=lambda kv: kv[1])

        return CardShotDiet(
            entropy=to_decimal(entropy, "0.01"),
            entropy_normalized=to_decimal(entropy_norm, "0.001"),
            primary_modes=primary_modes,
            top_play_type=top_name,
            top_play_type_freq=to_decimal(top_p, "0.001"),
        )

    def _build_rim_gravity(
        self, shot_zones: list[PlayerShotZones]
    ) -> CardRimGravity | None:
        """How much a player bends the defense toward the rim.

        Signals combined (each clamped to a reference upper bound so the
        composite lives on 0-100):
        - paint_touches / game (volume inside)
        - drives / game (attack-the-rim volume)
        - rim FG% lift vs. league average (finishing quality)
        - paint-touch pts/touch (scoring efficiency from paint)
        """
        touches = self._first(PlayerTouchesBreakdown)
        shooting = self._first(PlayerShootingTracking)

        paint_touches = touches.paint_touches if touches else None
        drives = shooting.drives if shooting else None
        paint_ppt = touches.paint_touch_pts_per_touch if touches else None

        # Rim FG% from the Restricted Area zone row (if present).
        rim_fg_pct = None
        for sz in shot_zones or []:
            if sz.zone and "restricted" in sz.zone.lower():
                rim_fg_pct = sz.fg_pct
                break

        if all(
            v is None for v in (paint_touches, drives, rim_fg_pct, paint_ppt)
        ):
            return None

        # Reference ceilings picked from top-of-league values.
        pt_norm = min(1.0, safe_float(paint_touches) / 25.0)
        dv_norm = min(1.0, safe_float(drives) / 20.0)
        rim_lift = safe_float(rim_fg_pct) - self._LEAGUE_AVG_RIM_FG_PCT
        # +15pp above league avg is elite, -5pp is poor.
        rim_norm = max(0.0, min(1.0, (rim_lift + 0.05) / 0.20))
        ppt_norm = min(1.0, safe_float(paint_ppt) / 1.0)

        score = 100.0 * (
            0.30 * pt_norm + 0.30 * dv_norm + 0.20 * rim_norm + 0.20 * ppt_norm
        )

        rim_delta = None
        if rim_fg_pct is not None:
            rim_delta = to_decimal(rim_lift, "0.001")

        return CardRimGravity(
            paint_touches_per_game=paint_touches,
            drives_per_game=drives,
            rim_fg_pct=rim_fg_pct,
            rim_fg_pct_vs_league=rim_delta,
            paint_pts_per_touch=paint_ppt,
            rim_gravity_score=to_decimal(score, "0.1"),
        )

    def _build_pass_funnel(
        self,
        current_career: PlayerCareerStats | None,
        season_stat: SeasonStats | None,
        gp: int,
    ) -> CardPassFunnel | None:
        """Passes -> potential assists -> actual assists -> hockey assists.

        `potential_to_actual_pct` captures teammate shot conversion on
        shots the player set up. `cascade_rate` (secondary assists per
        100 passes) captures chain playmaking — the player's pass starts
        an action that ends in an assist.
        """
        passing = self._first(PlayerPassingStats)
        if not passing:
            return None

        passes_made = passing.passes_made
        potential_ast = passing.potential_ast
        secondary_ast = passing.secondary_ast

        # Prefer per-game APG from current_career (already per-game).
        # Fall back to season_stat total_assists / gp for consistency.
        apg: Decimal | None = None
        if current_career and current_career.apg is not None:
            apg = current_career.apg
        elif season_stat and season_stat.total_assists is not None and gp > 0:
            apg = to_decimal(safe_float(season_stat.total_assists) / gp, "0.01")

        pm_f = safe_float(passes_made)
        pa_f = safe_float(potential_ast)
        ast_f = safe_float(apg)
        sa_f = safe_float(secondary_ast)

        pass_to_pot = (
            to_decimal(pa_f / pm_f * 100, "0.01") if pm_f > 0 and pa_f > 0 else None
        )
        pot_to_act = (
            to_decimal(ast_f / pa_f * 100, "0.01") if pa_f > 0 and ast_f > 0 else None
        )
        pass_to_act = (
            to_decimal(ast_f / pm_f * 100, "0.01") if pm_f > 0 and ast_f > 0 else None
        )
        cascade = (
            to_decimal(sa_f / pm_f * 100, "0.01") if pm_f > 0 and sa_f > 0 else None
        )

        return CardPassFunnel(
            passes_made=passes_made,
            potential_ast=potential_ast,
            ast=apg,
            secondary_ast=secondary_ast,
            pass_to_potential_pct=pass_to_pot,
            potential_to_actual_pct=pot_to_act,
            pass_to_actual_pct=pass_to_act,
            cascade_rate=cascade,
        )

    # ------------------------------------------------------------------
    # Batch 2: leverage / tempo / defense terrain signals
    # ------------------------------------------------------------------

    # A game counts as "leverage" when |plus_minus| <= this cutoff.
    # 15 is the common public-analytics threshold for "meaningful minutes"
    # without being so tight it rejects normal NBA blowouts.
    _LEVERAGE_PM_CUTOFF = 15

    # Late/early-season trend window. Uses the first N and last N games
    # of the season for the player when at least 2*N games are logged.
    _TREND_WINDOW = 10

    def _build_leverage_ts(self) -> CardLeverageTs | None:
        """Split a player's per-game TS% into leverage vs. blowout buckets.

        Per-game TS% = pts / (2 * (fga + 0.44 * fta)). Games with fga == 0
        are skipped (no shots attempted). Leverage = |plus_minus| <= 15.
        """
        rows = (
            self._db.query(GameStats)
            .filter(
                GameStats.player_id == self._player_id,
                GameStats.season == self._season,
            )
            .all()
        )
        if not rows:
            return None

        def _ts(pts: float, fga: float, fta: float) -> float | None:
            denom = 2.0 * (fga + 0.44 * fta)
            return pts / denom if denom > 0 else None

        all_num = 0.0
        all_den = 0.0
        lev_num = 0.0
        lev_den = 0.0
        blow_num = 0.0
        blow_den = 0.0
        lev_games = 0
        blow_games = 0

        for r in rows:
            pts = safe_float(r.points)
            fga = safe_float(r.fga)
            fta = safe_float(r.fta)
            pm = safe_float(r.plus_minus) if r.plus_minus is not None else None
            denom = 2.0 * (fga + 0.44 * fta)
            if denom <= 0:
                continue
            all_num += pts
            all_den += denom
            if pm is not None and abs(pm) <= self._LEVERAGE_PM_CUTOFF:
                lev_num += pts
                lev_den += denom
                lev_games += 1
            elif pm is not None:
                blow_num += pts
                blow_den += denom
                blow_games += 1

        if all_den <= 0:
            return None

        overall_ts = all_num / all_den
        leverage_ts = (lev_num / lev_den) if lev_den > 0 else None
        blowout_ts = (blow_num / blow_den) if blow_den > 0 else None
        delta = (
            (leverage_ts - overall_ts)
            if leverage_ts is not None
            else None
        )

        return CardLeverageTs(
            overall_ts_pct=to_decimal(overall_ts, "0.001"),
            leverage_ts_pct=(
                to_decimal(leverage_ts, "0.001") if leverage_ts is not None else None
            ),
            blowout_ts_pct=(
                to_decimal(blowout_ts, "0.001") if blowout_ts is not None else None
            ),
            ts_leverage_delta=(
                to_decimal(delta, "0.001") if delta is not None else None
            ),
            leverage_games=lev_games,
            blowout_games=blow_games,
        )

    def _build_possession_dwell(
        self, season_stat: SeasonStats | None, gp: int
    ) -> CardPossessionDwell | None:
        """Derive ball-holding efficiency from season totals.

        avg_sec_per_touch  = total_time_of_possession / total_touches
        pts_per_touch      = total_points / total_touches
        pts_per_second     = total_points / total_time_of_possession
        creation_per_second= (pts + 0.5 * ast) / time  (discount ast so
            we don't double-count a pass + teammate shot)
        dwell_score (0-100): 100 * pts_per_second / 0.45 (clamped). 0.45
            pts/sec is roughly top-of-league territory.
        """
        if not season_stat:
            return None
        touches = safe_float(season_stat.total_touches)
        time_poss = safe_float(season_stat.total_time_of_possession)
        pts = safe_float(season_stat.total_points)
        ast = safe_float(season_stat.total_assists)
        if touches <= 0 or time_poss <= 0:
            return None

        sec_per_touch = time_poss / touches
        pts_per_touch = pts / touches
        pts_per_second = pts / time_poss
        creation_per_second = (pts + 0.5 * ast) / time_poss

        # Reference ceiling: 0.45 pts/sec is near the top of the league.
        dwell_score = min(100.0, (pts_per_second / 0.45) * 100.0)

        return CardPossessionDwell(
            avg_sec_per_touch=to_decimal(sec_per_touch, "0.01"),
            pts_per_touch=to_decimal(pts_per_touch, "0.001"),
            pts_per_second=to_decimal(pts_per_second, "0.001"),
            creation_per_second=to_decimal(creation_per_second, "0.001"),
            dwell_efficiency_score=to_decimal(dwell_score, "0.1"),
        )

    def _build_mile_production(
        self, current_career: PlayerCareerStats | None, gp: int
    ) -> CardMileProduction | None:
        """Offensive output per mile traveled.

        Uses per-game distance from PlayerSpeedDistance. Production =
        ppg + apg. Also reports production per OFFENSIVE mile since the
        split is what a player runs to create, not what they run chasing.
        """
        sd = self._first(PlayerSpeedDistance)
        if not sd or sd.dist_miles is None or safe_float(sd.dist_miles) <= 0:
            return None

        ppg = safe_float(current_career.ppg if current_career else None)
        apg = safe_float(current_career.apg if current_career else None)
        if ppg <= 0 and apg <= 0:
            return None

        dist_miles = safe_float(sd.dist_miles)
        dist_miles_off = safe_float(sd.dist_miles_off)
        pts_ast = ppg + apg
        per_mile = pts_ast / dist_miles
        per_off_mile = (pts_ast / dist_miles_off) if dist_miles_off > 0 else None
        off_share = (dist_miles_off / dist_miles) if dist_miles > 0 else None

        return CardMileProduction(
            dist_miles_per_game=sd.dist_miles,
            dist_miles_off_share=(
                to_decimal(off_share, "0.001") if off_share is not None else None
            ),
            pts_ast_per_game=to_decimal(pts_ast, "0.01"),
            production_per_mile=to_decimal(per_mile, "0.01"),
            production_per_off_mile=(
                to_decimal(per_off_mile, "0.01") if per_off_mile is not None else None
            ),
        )

    def _build_late_season_trend(self) -> CardLateSeasonTrend | None:
        """Compare game_score in the first N games vs. the last N games.

        A fatigue/engagement proxy — NBA Stats does not expose per-
        quarter tracking at the ingest layer, so we use season-tails
        instead. Requires at least 2*N games with non-null game_score.
        """
        rows = (
            self._db.query(GameStats)
            .filter(
                GameStats.player_id == self._player_id,
                GameStats.season == self._season,
                GameStats.game_score.isnot(None),
            )
            .order_by(GameStats.game_date.asc())
            .all()
        )
        n = self._TREND_WINDOW
        if len(rows) < 2 * n:
            return None

        early = rows[:n]
        late = rows[-n:]

        def _avg(attr: str, sample: list[GameStats]) -> float:
            vals = [safe_float(getattr(g, attr)) for g in sample]
            return sum(vals) / len(vals) if vals else 0.0

        early_gs = _avg("game_score", early)
        late_gs = _avg("game_score", late)
        early_min = _avg("minutes", early)
        late_min = _avg("minutes", late)

        return CardLateSeasonTrend(
            early_games=n,
            late_games=n,
            early_game_score=to_decimal(early_gs, "0.01"),
            late_game_score=to_decimal(late_gs, "0.01"),
            trend_delta=to_decimal(late_gs - early_gs, "0.01"),
            early_minutes_avg=to_decimal(early_min, "0.01"),
            late_minutes_avg=to_decimal(late_min, "0.01"),
        )

    @staticmethod
    def _build_defensive_terrain(
        defense: PlayerDefensiveStats | None,
    ) -> CardDefensiveTerrain | None:
        """Weighted stopping-power across rim / mid / 3PT zones.

        Mid-range freq is inferred as max(0, 1 - rim_freq - three_freq)
        and uses overall_pct_plusminus as the best available proxy
        (there's no dedicated mid-range defense row). terrain_score
        maps the weighted plus/minus total to 0-100: +0.06 (league-
        leading suppression) -> ~90, 0 -> 50, -0.06 -> ~10.
        """
        if not defense:
            return None

        rim_freq = safe_float(defense.rim_freq)
        three_freq = safe_float(defense.three_pt_freq)
        mid_freq = max(0.0, 1.0 - rim_freq - three_freq)

        rim_pm = safe_float(defense.rim_pct_plusminus)
        three_pm = safe_float(defense.three_pt_pct_plusminus)
        # Overall_pct_plusminus covers all shots; we reuse it as the
        # best available mid-range proxy since rim/3PT cover the tails.
        overall_pm = safe_float(defense.overall_pct_plusminus)

        # Contribution = freq * (-plus_minus). Negative plus_minus =
        # opponent shoots worse than usual, which we want to reward.
        rim_contrib = rim_freq * (-rim_pm)
        mid_contrib = mid_freq * (-overall_pm)
        three_contrib = three_freq * (-three_pm)
        weighted = rim_contrib + mid_contrib + three_contrib

        # 0.06 ≈ 6 percentage points below league norm — elite defender.
        score = max(0.0, min(100.0, 50.0 + (weighted / 0.06) * 40.0))

        return CardDefensiveTerrain(
            rim_freq=defense.rim_freq,
            rim_plus_minus=defense.rim_pct_plusminus,
            rim_contribution=to_decimal(rim_contrib, "0.001"),
            mid_freq=to_decimal(mid_freq, "0.001"),
            mid_plus_minus=defense.overall_pct_plusminus,
            mid_contribution=to_decimal(mid_contrib, "0.001"),
            three_freq=defense.three_pt_freq,
            three_plus_minus=defense.three_pt_pct_plusminus,
            three_contribution=to_decimal(three_contrib, "0.001"),
            terrain_score=to_decimal(score, "0.1"),
        )

    @staticmethod
    def _build_contest_conversion(
        season_stat: SeasonStats | None,
        defense: PlayerDefensiveStats | None,
        gp: int,
    ) -> CardContestConversion | None:
        """Defensive disruption volume + conversion to forced misses.

        Scope mismatch caveat: contested_shots (from SeasonStats) counts
        every shot the player contested — including help contests on
        teammates' coverages. Defended FGA (from PlayerDefensiveStats)
        only counts shots where this player was the NEAREST defender.
        Surfacing both per-game rates preserves that distinction.
        """
        if not season_stat and not defense:
            return None
        gp_i = max(1, gp)

        contests = safe_float(season_stat.total_contested_shots) if season_stat else 0.0
        defended_fga = safe_float(defense.overall_d_fga) if defense else 0.0
        defended_fgm = safe_float(defense.overall_d_fgm) if defense else 0.0
        misses_forced = max(0.0, defended_fga - defended_fgm)

        if contests <= 0 and defended_fga <= 0:
            return None

        contests_pg = contests / gp_i if contests > 0 else None
        defended_pg = defended_fga / gp_i if defended_fga > 0 else None
        misses_pg = misses_forced / gp_i if defended_fga > 0 else None
        miss_rate = (
            (misses_forced / defended_fga) if defended_fga > 0 else None
        )

        # Volume ceiling ~15 contests/g, efficiency ceiling ~0.70 miss rate.
        vol_norm = min(1.0, (contests_pg or 0.0) / 15.0)
        eff_norm = min(1.0, max(0.0, ((miss_rate or 0.0) - 0.40) / 0.30))
        score = 100.0 * (0.5 * vol_norm + 0.5 * eff_norm)

        return CardContestConversion(
            contests_per_game=(
                to_decimal(contests_pg, "0.01") if contests_pg is not None else None
            ),
            defended_fga_per_game=(
                to_decimal(defended_pg, "0.01") if defended_pg is not None else None
            ),
            misses_forced_per_game=(
                to_decimal(misses_pg, "0.01") if misses_pg is not None else None
            ),
            miss_rate=(
                to_decimal(miss_rate, "0.001") if miss_rate is not None else None
            ),
            contest_to_miss_score=to_decimal(score, "0.1"),
        )

    # ------------------------------------------------------------------
    # Batch 3: lineup buoyancy + scheme robustness
    # ------------------------------------------------------------------

    # Below this per-lineup minute floor we ignore the lineup — tercile
    # math on 3-minute samples is noise, not signal.
    _BUOYANCY_MIN_LINEUP_MINUTES = Decimal("20")
    # Need at least this many qualifying lineups to report terciles.
    _BUOYANCY_MIN_LINEUPS = 4
    # Per-play-type sample floor for robustness analysis. Under 25 poss
    # the PPP is too noisy to include in a variance comparison.
    _ROBUSTNESS_MIN_POSSESSIONS = 25

    def _build_lineup_buoyancy(self) -> CardLineupBuoyancy | None:
        """Floor-raiser vs ceiling-raiser signal across a player's lineups.

        Partitions qualifying lineups (>= 20 min) into terciles by net
        rating, then minutes-weights each tercile. A high worst-tercile
        NRtg means the player keeps bad combos afloat (floor raiser);
        a dominant best-tercile NRtg means they amplify already-good
        combos (ceiling raiser).
        """
        lineups = (
            self._db.query(LineupStats)
            .filter(
                LineupStats.season == self._season,
                or_(
                    LineupStats.player1_id == self._player_id,
                    LineupStats.player2_id == self._player_id,
                    LineupStats.player3_id == self._player_id,
                    LineupStats.player4_id == self._player_id,
                    LineupStats.player5_id == self._player_id,
                ),
            )
            .all()
        )
        if not lineups:
            return None

        qualifying = [
            lu
            for lu in lineups
            if lu.minutes is not None
            and lu.net_rating is not None
            and lu.minutes >= self._BUOYANCY_MIN_LINEUP_MINUTES
        ]
        if len(qualifying) < self._BUOYANCY_MIN_LINEUPS:
            return None

        # Sort ascending by net rating so the worst-performing lineups
        # come first. Tercile split by count, not by minutes, since we
        # want a representative sample of bad-lineup outcomes.
        qualifying.sort(key=lambda lu: lu.net_rating)
        n = len(qualifying)
        tercile_size = max(1, n // 3)
        worst = qualifying[:tercile_size]
        best = qualifying[-tercile_size:]

        def _weighted_avg(rows: list[LineupStats]) -> tuple[Decimal, Decimal]:
            total_min = sum((lu.minutes for lu in rows), Decimal("0"))
            if total_min <= 0:
                return Decimal("0"), Decimal("0")
            weighted = sum(
                (lu.net_rating * lu.minutes for lu in rows), Decimal("0")
            )
            return (weighted / total_min).quantize(Decimal("0.01")), total_min.quantize(Decimal("0.01"))

        worst_net, worst_min = _weighted_avg(worst)
        best_net, best_min = _weighted_avg(best)
        median_net = qualifying[n // 2].net_rating
        spread = (best_net - worst_net).quantize(Decimal("0.01"))
        total_qual_min = sum(
            (lu.minutes for lu in qualifying), Decimal("0")
        ).quantize(Decimal("0.01"))

        # Normalize NRtgs to 0-100 for an intuitive floor/ceiling read.
        # -15 -> 0, +15 -> 100, clamped. Same scale for both so they're
        # directly comparable on the UI.
        def _score(nrtg: Decimal) -> float:
            return max(0.0, min(100.0, (float(nrtg) + 15.0) / 30.0 * 100.0))

        floor_score = _score(worst_net)
        ceiling_score = _score(best_net)

        # Classification. Thresholds chosen to line up with the 0-100
        # score scale above and to require clear separation before
        # labeling someone a specialist.
        if floor_score >= 60 and ceiling_score >= 75:
            buoyancy_type = "Two-Way Lift"
        elif floor_score >= 60:
            buoyancy_type = "Floor Raiser"
        elif ceiling_score >= 75 and floor_score < 50:
            buoyancy_type = "Ceiling Amplifier"
        elif ceiling_score < 50 and floor_score < 40:
            buoyancy_type = "Passenger"
        else:
            buoyancy_type = "Neutral"

        return CardLineupBuoyancy(
            total_lineups=n,
            qualifying_minutes=total_qual_min,
            worst_tercile_net_rtg=worst_net,
            worst_tercile_minutes=worst_min,
            best_tercile_net_rtg=best_net,
            best_tercile_minutes=best_min,
            median_lineup_net_rtg=median_net,
            lineup_spread=spread,
            floor_score=to_decimal(floor_score, "0.1"),
            ceiling_score=to_decimal(ceiling_score, "0.1"),
            buoyancy_type=buoyancy_type,
        )

    def _build_scheme_robustness(
        self, play_types: SeasonPlayTypeStats | None
    ) -> CardSchemeRobustness | None:
        """Coefficient-of-variation across the player's top 3 play types.

        Low CV on high PPP = scheme-proof scorer. High CV = one mode
        carries them and the rest collapse (scheme-dependent). Uses
        a 25-poss floor to keep noisy minor modes out of the variance.
        """
        if not play_types:
            return None

        attrs = [
            ("isolation", "isolation_freq", "isolation_ppp", "isolation_poss"),
            ("pnr_ball_handler", "pnr_ball_handler_freq", "pnr_ball_handler_ppp", "pnr_ball_handler_poss"),
            ("pnr_roll_man", "pnr_roll_man_freq", "pnr_roll_man_ppp", "pnr_roll_man_poss"),
            ("post_up", "post_up_freq", "post_up_ppp", "post_up_poss"),
            ("spot_up", "spot_up_freq", "spot_up_ppp", "spot_up_poss"),
            ("transition", "transition_freq", "transition_ppp", "transition_poss"),
            ("cut", "cut_freq", "cut_ppp", "cut_poss"),
            ("off_screen", "off_screen_freq", "off_screen_ppp", "off_screen_poss"),
            ("handoff", "handoff_freq", "handoff_ppp", "handoff_poss"),
        ]
        candidates: list[tuple[str, float, float, int]] = []
        for name, freq_attr, ppp_attr, poss_attr in attrs:
            poss = getattr(play_types, poss_attr, None) or 0
            freq = safe_float(getattr(play_types, freq_attr, None))
            ppp = safe_float(getattr(play_types, ppp_attr, None))
            if poss >= self._ROBUSTNESS_MIN_POSSESSIONS and freq > 0 and ppp > 0:
                candidates.append((name, freq, ppp, poss))

        if len(candidates) < 3:
            return None

        # Pick the top 3 by frequency share.
        candidates.sort(key=lambda row: row[1], reverse=True)
        top3 = candidates[:3]
        names = [row[0] for row in top3]
        ppps = [row[2] for row in top3]

        mean_ppp = sum(ppps) / len(ppps)
        variance = sum((p - mean_ppp) ** 2 for p in ppps) / len(ppps)
        std = math.sqrt(variance)
        cv = std / mean_ppp if mean_ppp > 0 else 0.0

        # 0.20 CV = essentially scheme-dependent (one mode >> others).
        # 0.02 CV = tightly clustered, scheme-proof.
        collapse_risk = max(0.0, min(100.0, cv / 0.20 * 100.0))
        robustness = 100.0 - collapse_risk

        return CardSchemeRobustness(
            top_play_types=names,
            top_play_type_ppps=[to_decimal(p, "0.001") for p in ppps],
            ppp_mean=to_decimal(mean_ppp, "0.001"),
            ppp_std=to_decimal(std, "0.001"),
            coefficient_of_variation=to_decimal(cv, "0.001"),
            collapse_risk_score=to_decimal(collapse_risk, "0.1"),
            robustness_score=to_decimal(robustness, "0.1"),
        )

