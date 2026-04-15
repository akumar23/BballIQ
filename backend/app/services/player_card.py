"""Service layer for the player card endpoint.

Orchestrates all database queries and computation (portability, championship,
luck-adjusted, scheme compatibility, opponent tiers, lineup context) required
to build the comprehensive PlayerCardData response.
"""

from __future__ import annotations

import logging
from decimal import Decimal

from sqlalchemy import or_
from sqlalchemy.orm import Session

from app.models import (
    ContextualizedImpact,
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
    CardAdvanced,
    CardAdjustmentStep,
    CardAllInOne,
    CardCareerSeason,
    CardChampionship,
    CardChampionshipPillar,
    CardConsistency,
    CardContextualized,
    CardDefenderDistanceEntry,
    CardDefenseOverview,
    CardDefenseZone,
    CardDefensive,
    CardDefensivePlayType,
    CardDefensivePlayTypes,
    CardGameLog,
    CardImpact,
    CardIsoDefense,
    CardLineup,
    CardLineupContext,
    CardLuckAdjusted,
    CardMatchup,
    CardOnOff,
    CardOpponentShooting,
    CardOpponentShootingBucket,
    CardOpponentTierEntry,
    CardPassing,
    CardPlayoffProjection,
    CardPlayType,
    CardPlayTypes,
    CardPortability,
    CardRadar,
    CardReboundingTracking,
    CardSchemeScore,
    CardShotZone,
    CardSpeedDistance,
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
        card_defensive = self._build_defensive(defense, season_stat, gp)
        card_career = self._build_career(career_rows)

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
            overview=_build_defense_overview(season_stat, defense, gp),
        )

    def _build_career(
        self, career_rows: list[PlayerCareerStats]
    ) -> list[CardCareerSeason]:
        computed_by_season = {
            row.season: row
            for row in self._db.query(PlayerComputedAdvanced)
            .filter(PlayerComputedAdvanced.player_id == self._player_id)
            .all()
        }
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
        return card_portability, portability_score

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

        playoff_proj = CardPlayoffProjection(
            projected_ppg=to_decimal(proj_ppg),
            projected_ts=to_decimal(proj_ts, "0.001"),
            reg_ppg=to_decimal(reg_ppg),
            reg_ts=to_decimal(reg_ts, "0.001"),
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

        FULL_RELIABILITY_MINUTES = Decimal("200")

        def _lineup_ctx_net(raw_net: Decimal | None, minutes: Decimal | None) -> Decimal:
            if raw_net is None:
                return team_baseline
            mins = minutes or Decimal("0")
            ratio = mins / FULL_RELIABILITY_MINUTES
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
