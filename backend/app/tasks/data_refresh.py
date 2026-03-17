"""Celery tasks for daily NBA data refresh.

These tasks wrap the existing fetch scripts to run as scheduled background jobs.
"""

import logging
from datetime import datetime

from celery import chain, group

from app.core.celery_app import celery_app
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)

# Default season - should be updated at the start of each NBA season
DEFAULT_SEASON = "2024-25"


def get_current_season() -> str:
    """Determine the current NBA season based on the date.

    NBA season typically starts in October and ends in June.
    A season like 2024-25 runs from October 2024 to June 2025.
    """
    now = datetime.utcnow()
    year = now.year
    month = now.month

    # If we're in Jan-June, we're in the second half of the season
    if month <= 6:
        return f"{year - 1}-{str(year)[-2:]}"
    # If we're in Oct-Dec, we're in the first half of the season
    elif month >= 10:
        return f"{year}-{str(year + 1)[-2:]}"
    # July-September is offseason, use previous season
    else:
        return f"{year - 1}-{str(year)[-2:]}"


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
)
def refresh_tracking_data(self, season: str | None = None) -> dict:
    """Fetch tracking data and store in database.

    This is the main data fetch that populates player stats.
    Must run before impact and play type tasks.

    Args:
        season: NBA season string (e.g., "2024-25"). Defaults to current season.

    Returns:
        dict with status and player count
    """
    # Import here to avoid circular imports and ensure fresh module state
    from decimal import Decimal

    from app.core.config import settings
    from app.models import Per75Stats, Player, SeasonStats
    from app.services.metrics import MetricsCalculator
    from app.services.nba_data import NBADataService
    from app.services.per_75_calculator import per_75_calculator
    from app.services.rate_limiter import CircuitBreakerError, RateLimitError

    season = season or get_current_season()
    logger.info("Starting tracking data refresh for season %s", season)

    db = SessionLocal()
    try:
        service = NBADataService(bypass_cache=True)

        # Fetch tracking data
        try:
            tracking_data = service.fetch_all_tracking_data(season)
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch tracking data: %s", e)
            raise self.retry(exc=e)

        if not tracking_data:
            logger.error("No tracking data fetched for season %s", season)
            return {"status": "error", "message": "No tracking data fetched"}

        logger.info("Fetched data for %d players", len(tracking_data))

        # Calculate league averages
        total_touches = sum(p.touches for p in tracking_data.values())
        league_avg_touches = Decimal(total_touches) / Decimal(len(tracking_data))
        calculator = MetricsCalculator(league_avg_touches)

        processed = 0
        errors = 0

        for player_id, data in tracking_data.items():
            try:
                # Upsert player
                player = db.query(Player).filter(Player.nba_id == player_id).first()
                if not player:
                    player = Player(
                        nba_id=player_id,
                        name=data.player_name,
                        team_abbreviation=data.team_abbreviation,
                        active=True,
                    )
                    db.add(player)
                    db.flush()

                # Calculate rates
                if data.touches > 0:
                    assist_rate = Decimal(data.assists) / Decimal(data.touches)
                    turnover_rate = Decimal(data.turnovers) / Decimal(data.touches)
                    ft_rate = Decimal(data.fta) / Decimal(data.touches)
                else:
                    assist_rate = turnover_rate = ft_rate = Decimal(0)

                # Calculate metrics
                offensive_metric = calculator.calculate_offensive_metric(
                    points_per_touch=data.points_per_touch,
                    assist_rate=assist_rate,
                    turnover_rate=turnover_rate,
                    ft_rate=ft_rate,
                    total_touches=data.touches,
                )

                est_def_possessions = int(data.minutes * 2)

                if est_def_possessions > 0:
                    deflections_per_100 = Decimal(data.deflections * 100) / Decimal(est_def_possessions)
                    total_contests = data.contested_shots_2pt + data.contested_shots_3pt
                    contests_per_100 = Decimal(total_contests * 100) / Decimal(est_def_possessions)
                    charges_per_100 = Decimal(data.charges_drawn * 100) / Decimal(est_def_possessions)
                    loose_balls_per_100 = Decimal(data.loose_balls_recovered * 100) / Decimal(est_def_possessions)
                else:
                    deflections_per_100 = contests_per_100 = charges_per_100 = loose_balls_per_100 = Decimal(0)

                defensive_metric = calculator.calculate_defensive_metric(
                    deflections_per_100=deflections_per_100,
                    contests_per_100=contests_per_100,
                    steals_per_100=Decimal(0),
                    charges_per_100=charges_per_100,
                    loose_balls_per_100=loose_balls_per_100,
                    total_possessions=est_def_possessions,
                )

                overall_metric = (
                    offensive_metric * Decimal("0.6") + defensive_metric * Decimal("0.4")
                    if offensive_metric > 0 or defensive_metric > 0
                    else Decimal(0)
                )

                # Upsert season stats
                season_stats = (
                    db.query(SeasonStats)
                    .filter(SeasonStats.player_id == player.id, SeasonStats.season == season)
                    .first()
                )

                if not season_stats:
                    season_stats = SeasonStats(player_id=player.id, season=season)
                    db.add(season_stats)

                # Update all stats fields
                season_stats.games_played = data.games_played
                season_stats.total_minutes = data.minutes
                season_stats.total_points = data.points
                season_stats.total_assists = data.assists
                season_stats.total_rebounds = data.rebounds
                season_stats.total_offensive_rebounds = data.offensive_rebounds
                season_stats.total_defensive_rebounds = data.defensive_rebounds
                season_stats.total_steals = data.steals
                season_stats.total_blocks = data.blocks
                season_stats.total_turnovers = data.turnovers
                season_stats.total_fgm = data.fgm
                season_stats.total_fga = data.fga
                season_stats.total_fg3m = data.fg3m
                season_stats.total_fg3a = data.fg3a
                season_stats.total_ftm = data.ftm
                season_stats.total_fta = data.fta
                season_stats.total_plus_minus = data.plus_minus
                season_stats.total_touches = data.touches
                season_stats.total_front_court_touches = data.front_court_touches
                season_stats.total_time_of_possession = data.time_of_possession
                season_stats.avg_points_per_touch = data.points_per_touch
                season_stats.total_deflections = data.deflections
                season_stats.total_contested_shots = data.contested_shots_2pt + data.contested_shots_3pt
                season_stats.total_contested_shots_2pt = data.contested_shots_2pt
                season_stats.total_contested_shots_3pt = data.contested_shots_3pt
                season_stats.total_charges_drawn = data.charges_drawn
                season_stats.total_loose_balls_recovered = data.loose_balls_recovered
                season_stats.total_box_outs = data.box_outs
                season_stats.total_box_outs_off = data.box_outs_off
                season_stats.total_box_outs_def = data.box_outs_def
                season_stats.total_screen_assists = data.screen_assists
                season_stats.total_screen_assist_pts = data.screen_assist_pts
                season_stats.estimated_possessions = est_def_possessions
                season_stats.offensive_metric = offensive_metric
                season_stats.defensive_metric = defensive_metric
                season_stats.overall_metric = overall_metric

                db.flush()

                # Calculate per-75 stats
                per_75_data = per_75_calculator.calculate_all(
                    possessions=est_def_possessions,
                    points=data.points,
                    fgm=data.fgm,
                    fga=data.fga,
                    fg3m=data.fg3m,
                    fg3a=data.fg3a,
                    ftm=data.ftm,
                    fta=data.fta,
                    assists=data.assists,
                    turnovers=data.turnovers,
                    rebounds=data.rebounds,
                    offensive_rebounds=data.offensive_rebounds,
                    defensive_rebounds=data.defensive_rebounds,
                    steals=data.steals,
                    blocks=data.blocks,
                    deflections=data.deflections,
                    contested_shots=data.contested_shots_2pt + data.contested_shots_3pt,
                    contested_2pt=data.contested_shots_2pt,
                    contested_3pt=data.contested_shots_3pt,
                    charges_drawn=data.charges_drawn,
                    loose_balls=data.loose_balls_recovered,
                    box_outs=data.box_outs,
                    screen_assists=data.screen_assists,
                    touches=data.touches,
                    front_court_touches=data.front_court_touches,
                )

                per_75_stats = (
                    db.query(Per75Stats)
                    .filter(Per75Stats.season_stats_id == season_stats.id)
                    .first()
                )

                if not per_75_stats:
                    per_75_stats = Per75Stats(season_stats_id=season_stats.id, season=season)
                    db.add(per_75_stats)

                # Update per-75 stats
                per_75_stats.pts_per_75 = per_75_data.pts_per_75
                per_75_stats.fgm_per_75 = per_75_data.fgm_per_75
                per_75_stats.fga_per_75 = per_75_data.fga_per_75
                per_75_stats.fg3m_per_75 = per_75_data.fg3m_per_75
                per_75_stats.fg3a_per_75 = per_75_data.fg3a_per_75
                per_75_stats.ftm_per_75 = per_75_data.ftm_per_75
                per_75_stats.fta_per_75 = per_75_data.fta_per_75
                per_75_stats.ast_per_75 = per_75_data.ast_per_75
                per_75_stats.tov_per_75 = per_75_data.tov_per_75
                per_75_stats.reb_per_75 = per_75_data.reb_per_75
                per_75_stats.oreb_per_75 = per_75_data.oreb_per_75
                per_75_stats.dreb_per_75 = per_75_data.dreb_per_75
                per_75_stats.stl_per_75 = per_75_data.stl_per_75
                per_75_stats.blk_per_75 = per_75_data.blk_per_75
                per_75_stats.deflections_per_75 = per_75_data.deflections_per_75
                per_75_stats.contested_shots_per_75 = per_75_data.contested_shots_per_75
                per_75_stats.contested_2pt_per_75 = per_75_data.contested_2pt_per_75
                per_75_stats.contested_3pt_per_75 = per_75_data.contested_3pt_per_75
                per_75_stats.charges_drawn_per_75 = per_75_data.charges_drawn_per_75
                per_75_stats.loose_balls_per_75 = per_75_data.loose_balls_per_75
                per_75_stats.box_outs_per_75 = per_75_data.box_outs_per_75
                per_75_stats.screen_assists_per_75 = per_75_data.screen_assists_per_75
                per_75_stats.touches_per_75 = per_75_data.touches_per_75
                per_75_stats.front_court_touches_per_75 = per_75_data.front_court_touches_per_75
                per_75_stats.possessions_used = per_75_data.possessions_used

                processed += 1

            except Exception as e:
                logger.error("Error processing player %d: %s", player_id, e)
                errors += 1

        db.commit()

        # Calculate percentiles
        stats = (
            db.query(SeasonStats)
            .filter(SeasonStats.season == season, SeasonStats.offensive_metric > 0)
            .all()
        )

        if stats:
            off_sorted = sorted(stats, key=lambda x: x.offensive_metric or 0)
            for i, stat in enumerate(off_sorted):
                stat.offensive_percentile = int((i / len(off_sorted)) * 100)

            def_sorted = sorted(stats, key=lambda x: x.defensive_metric or 0)
            for i, stat in enumerate(def_sorted):
                stat.defensive_percentile = int((i / len(def_sorted)) * 100)

            db.commit()

        logger.info("Tracking data refresh completed: %d processed, %d errors", processed, errors)
        return {"status": "success", "processed": processed, "errors": errors, "season": season}

    except Exception as e:
        logger.exception("Tracking data refresh failed: %s", e)
        db.rollback()
        raise

    finally:
        db.close()


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
)
def refresh_impact_data(self, season: str | None = None) -> dict:
    """Fetch impact data and store in database.

    Args:
        season: NBA season string. Defaults to current season.

    Returns:
        dict with status and player count
    """
    from app.models import ContextualizedImpact, Player, PlayerOnOffStats
    from app.services.impact_calculator import ImpactCalculator
    from app.services.nba_data import NBADataService
    from app.services.rate_limiter import CircuitBreakerError, RateLimitError

    season = season or get_current_season()
    logger.info("Starting impact data refresh for season %s", season)

    db = SessionLocal()
    try:
        service = NBADataService(bypass_cache=True)

        # Fetch lineup data
        try:
            lineup_data = service.fetch_lineup_data(season)
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch lineup data: %s", e)
            raise self.retry(exc=e)

        # Fetch on/off data
        try:
            on_off_data = service.get_all_on_off_stats(season)
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch on/off data: %s", e)
            raise self.retry(exc=e)

        # Calculate impact
        calculator = ImpactCalculator(lineup_data, on_off_data)
        impacts = calculator.calculate_all_impacts()

        processed = 0
        errors = 0

        for player_id, on_off in on_off_data.items():
            try:
                player = db.query(Player).filter(Player.nba_id == player_id).first()
                if not player:
                    continue

                # Upsert on/off stats
                on_off_stats = (
                    db.query(PlayerOnOffStats)
                    .filter(PlayerOnOffStats.player_id == player.id, PlayerOnOffStats.season == season)
                    .first()
                )

                if not on_off_stats:
                    on_off_stats = PlayerOnOffStats(player_id=player.id, season=season)
                    db.add(on_off_stats)

                on_off_stats.on_court_minutes = on_off.on_court_min
                on_off_stats.on_court_plus_minus = on_off.on_court_plus_minus
                on_off_stats.on_court_off_rating = on_off.on_court_off_rating
                on_off_stats.on_court_def_rating = on_off.on_court_def_rating
                on_off_stats.on_court_net_rating = on_off.on_court_net_rating
                on_off_stats.off_court_minutes = on_off.off_court_min
                on_off_stats.off_court_plus_minus = on_off.off_court_plus_minus
                on_off_stats.off_court_off_rating = on_off.off_court_off_rating
                on_off_stats.off_court_def_rating = on_off.off_court_def_rating
                on_off_stats.off_court_net_rating = on_off.off_court_net_rating
                on_off_stats.plus_minus_diff = on_off.plus_minus_diff
                on_off_stats.off_rating_diff = on_off.off_rating_diff
                on_off_stats.def_rating_diff = on_off.def_rating_diff
                on_off_stats.net_rating_diff = on_off.net_rating_diff

                # Upsert impact data
                impact_data = impacts.get(player_id)
                if impact_data:
                    impact = (
                        db.query(ContextualizedImpact)
                        .filter(ContextualizedImpact.player_id == player.id, ContextualizedImpact.season == season)
                        .first()
                    )

                    if not impact:
                        impact = ContextualizedImpact(player_id=player.id, season=season)
                        db.add(impact)

                    impact.raw_net_rating_diff = impact_data.raw_net_rating_diff
                    impact.raw_off_rating_diff = impact_data.raw_off_rating_diff
                    impact.raw_def_rating_diff = impact_data.raw_def_rating_diff
                    impact.avg_teammate_net_rating = impact_data.avg_teammate_net_rating
                    impact.teammate_adjustment = impact_data.teammate_adjustment
                    impact.pct_minutes_vs_starters = impact_data.pct_minutes_vs_starters
                    impact.opponent_quality_factor = impact_data.opponent_quality_factor
                    impact.total_on_court_minutes = impact_data.total_on_court_minutes
                    impact.reliability_factor = impact_data.reliability_factor
                    impact.contextualized_off_impact = impact_data.contextualized_off_impact
                    impact.contextualized_def_impact = impact_data.contextualized_def_impact
                    impact.contextualized_net_impact = impact_data.contextualized_net_impact

                processed += 1

            except Exception as e:
                logger.error("Error processing player %d: %s", player_id, e)
                errors += 1

        db.commit()

        # Calculate percentiles
        impacts_list = (
            db.query(ContextualizedImpact)
            .filter(ContextualizedImpact.season == season, ContextualizedImpact.contextualized_net_impact.isnot(None))
            .all()
        )

        if impacts_list:
            net_sorted = sorted(impacts_list, key=lambda x: x.contextualized_net_impact or 0)
            for i, impact in enumerate(net_sorted):
                impact.impact_percentile = int((i / len(net_sorted)) * 100)

            off_sorted = sorted(impacts_list, key=lambda x: x.contextualized_off_impact or 0)
            for i, impact in enumerate(off_sorted):
                impact.offensive_impact_percentile = int((i / len(off_sorted)) * 100)

            def_sorted = sorted(impacts_list, key=lambda x: x.contextualized_def_impact or 0)
            for i, impact in enumerate(def_sorted):
                impact.defensive_impact_percentile = int(((len(def_sorted) - i - 1) / len(def_sorted)) * 100)

            db.commit()

        logger.info("Impact data refresh completed: %d processed, %d errors", processed, errors)
        return {"status": "success", "processed": processed, "errors": errors, "season": season}

    except Exception as e:
        logger.exception("Impact data refresh failed: %s", e)
        db.rollback()
        raise

    finally:
        db.close()


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
)
def refresh_play_type_data(self, season: str | None = None) -> dict:
    """Fetch play type data and store in database.

    Args:
        season: NBA season string. Defaults to current season.

    Returns:
        dict with status and player count
    """
    from decimal import Decimal

    from app.models import Player, SeasonPlayTypeStats
    from app.services.nba_data import NBADataService, PLAY_TYPE_MAPPING
    from app.services.rate_limiter import CircuitBreakerError, RateLimitError

    season = season or get_current_season()
    logger.info("Starting play type data refresh for season %s", season)

    MIN_POSS_THRESHOLD = 50

    db = SessionLocal()
    try:
        service = NBADataService(bypass_cache=True)

        # Fetch play type data
        try:
            play_type_data = service.fetch_all_play_type_data(season)
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch play type data: %s", e)
            raise self.retry(exc=e)

        processed = 0
        errors = 0

        for player_id, data in play_type_data.items():
            try:
                player = db.query(Player).filter(Player.nba_id == player_id).first()
                if not player:
                    continue

                stats = (
                    db.query(SeasonPlayTypeStats)
                    .filter(SeasonPlayTypeStats.player_id == player.id, SeasonPlayTypeStats.season == season)
                    .first()
                )

                if not stats:
                    stats = SeasonPlayTypeStats(player_id=player.id, season=season)
                    db.add(stats)

                stats.total_poss = data.total_poss

                for field_name in PLAY_TYPE_MAPPING.keys():
                    metrics = getattr(data, field_name)
                    if metrics is None:
                        continue

                    setattr(stats, f"{field_name}_poss", metrics.possessions)
                    setattr(stats, f"{field_name}_pts", metrics.points)
                    setattr(stats, f"{field_name}_fgm", metrics.fgm)
                    setattr(stats, f"{field_name}_fga", metrics.fga)

                    # Calculate PPP, FG%, frequency
                    ppp = fg_pct = freq = None
                    if metrics.possessions and metrics.possessions > 0 and metrics.points is not None:
                        ppp = Decimal(str(metrics.points)) / Decimal(str(metrics.possessions))
                    if metrics.fga and metrics.fga > 0 and metrics.fgm is not None:
                        fg_pct = Decimal(str(metrics.fgm)) / Decimal(str(metrics.fga))
                    if data.total_poss and data.total_poss > 0 and metrics.possessions:
                        freq = Decimal(str(metrics.possessions)) / Decimal(str(data.total_poss))

                    setattr(stats, f"{field_name}_ppp", ppp)
                    setattr(stats, f"{field_name}_fg_pct", fg_pct)
                    setattr(stats, f"{field_name}_freq", freq)

                    if field_name == "spot_up" and metrics.fg3m is not None:
                        setattr(stats, "spot_up_fg3m", metrics.fg3m)
                        setattr(stats, "spot_up_fg3a", metrics.fg3a)
                        if metrics.fg3a and metrics.fg3a > 0:
                            fg3_pct = Decimal(str(metrics.fg3m)) / Decimal(str(metrics.fg3a))
                            setattr(stats, "spot_up_fg3_pct", fg3_pct)

                processed += 1

            except Exception as e:
                logger.error("Error processing player %d: %s", player_id, e)
                errors += 1

        db.commit()

        # Calculate percentiles
        stats_list = db.query(SeasonPlayTypeStats).filter(SeasonPlayTypeStats.season == season).all()

        play_types = [
            "isolation", "pnr_ball_handler", "pnr_roll_man", "post_up",
            "spot_up", "transition", "cut", "off_screen",
        ]

        for play_type in play_types:
            poss_attr = f"{play_type}_poss"
            ppp_attr = f"{play_type}_ppp"
            percentile_attr = f"{play_type}_ppp_percentile"

            qualified = [
                s for s in stats_list
                if (getattr(s, poss_attr) or 0) >= MIN_POSS_THRESHOLD
                and getattr(s, ppp_attr) is not None
            ]

            if not qualified:
                continue

            sorted_players = sorted(qualified, key=lambda x: getattr(x, ppp_attr) or 0)
            for i, stat in enumerate(sorted_players):
                setattr(stat, percentile_attr, int((i / len(sorted_players)) * 100))

        db.commit()

        logger.info("Play type data refresh completed: %d processed, %d errors", processed, errors)
        return {"status": "success", "processed": processed, "errors": errors, "season": season}

    except Exception as e:
        logger.exception("Play type data refresh failed: %s", e)
        db.rollback()
        raise

    finally:
        db.close()


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
)
def refresh_advanced_data(self, season: str | None = None) -> dict:
    """Fetch advanced stats, shot zones, clutch, and defensive data.

    Args:
        season: NBA season string. Defaults to current season.

    Returns:
        dict with status and player count
    """
    from decimal import Decimal

    from app.models import Player
    from app.models.advanced_stats import PlayerAdvancedStats
    from app.models.clutch_stats import PlayerClutchStats as PlayerClutchStatsModel
    from app.models.defensive_matchups import PlayerDefensiveStats as PlayerDefensiveStatsModel
    from app.models.shot_zones import PlayerShotZones as PlayerShotZonesModel
    from app.services.nba_data import NBADataService
    from app.services.rate_limiter import CircuitBreakerError, RateLimitError

    season = season or get_current_season()
    logger.info("Starting advanced data refresh for season %s", season)

    def safe_decimal(value, default=None):
        if value is None:
            return default
        try:
            return Decimal(str(value))
        except Exception:
            return default

    def safe_int(value, default=None):
        if value is None:
            return default
        try:
            return int(value)
        except (ValueError, TypeError):
            return default

    db = SessionLocal()
    try:
        service = NBADataService(bypass_cache=True)

        # Fetch advanced stats
        try:
            advanced_data = service.get_advanced_stats(season)
            advanced_by_player = {p["PLAYER_ID"]: p for p in advanced_data}
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch advanced stats: %s", e)
            raise self.retry(exc=e)

        # Fetch clutch stats
        try:
            clutch_data = service.get_clutch_stats(season)
            clutch_by_player = {p["PLAYER_ID"]: p for p in clutch_data}
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch clutch stats: %s", e)
            clutch_by_player = {}

        # Fetch defensive stats
        try:
            overall_defense = service.get_defensive_stats(season)
            overall_def_by_player = {p["CLOSE_DEF_PERSON_ID"]: p for p in overall_defense}
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch overall defensive stats: %s", e)
            overall_def_by_player = {}

        try:
            rim_defense = service.get_rim_protection_stats(season)
            rim_def_by_player = {p["CLOSE_DEF_PERSON_ID"]: p for p in rim_defense}
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch rim protection stats: %s", e)
            rim_def_by_player = {}

        try:
            three_pt_defense = service.get_three_point_defense_stats(season)
            three_pt_def_by_player = {p["CLOSE_DEF_PERSON_ID"]: p for p in three_pt_defense}
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch 3PT defensive stats: %s", e)
            three_pt_def_by_player = {}

        try:
            iso_defense = service.get_defensive_play_type_stats("Isolation", season)
            iso_def_by_player = {p["PLAYER_ID"]: p for p in iso_defense}
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch isolation defense stats: %s", e)
            iso_def_by_player = {}

        # Fetch shot zone data
        try:
            shot_data = service.get_shot_location_stats(season)
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch shot location stats: %s", e)
            shot_data = []

        try:
            league_averages = service.get_league_shot_averages(season)
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch league shot averages: %s", e)
            league_averages = {}

        # Collect all player IDs
        all_player_ids = set()
        all_player_ids.update(advanced_by_player.keys())
        all_player_ids.update(clutch_by_player.keys())
        all_player_ids.update(overall_def_by_player.keys())
        all_player_ids.update(rim_def_by_player.keys())
        all_player_ids.update(three_pt_def_by_player.keys())
        all_player_ids.update(iso_def_by_player.keys())

        processed = 0
        errors = 0

        for player_id in all_player_ids:
            try:
                player = db.query(Player).filter(Player.nba_id == player_id).first()
                if not player:
                    continue

                # Upsert advanced stats
                adv = advanced_by_player.get(player_id)
                if adv:
                    adv_stats = (
                        db.query(PlayerAdvancedStats)
                        .filter(PlayerAdvancedStats.player_id == player.id, PlayerAdvancedStats.season == season)
                        .first()
                    )
                    if not adv_stats:
                        adv_stats = PlayerAdvancedStats(player_id=player.id, season=season)
                        db.add(adv_stats)

                    adv_stats.ts_pct = safe_decimal(adv.get("TS_PCT"))
                    adv_stats.efg_pct = safe_decimal(adv.get("EFG_PCT"))
                    adv_stats.usg_pct = safe_decimal(adv.get("USG_PCT"))
                    adv_stats.off_rating = safe_decimal(adv.get("OFF_RATING"))
                    adv_stats.def_rating = safe_decimal(adv.get("DEF_RATING"))
                    adv_stats.net_rating = safe_decimal(adv.get("NET_RATING"))
                    adv_stats.pace = safe_decimal(adv.get("PACE"))
                    adv_stats.pie = safe_decimal(adv.get("PIE"))
                    adv_stats.ast_pct = safe_decimal(adv.get("AST_PCT"))
                    adv_stats.ast_to = safe_decimal(adv.get("AST_TO"))
                    adv_stats.ast_ratio = safe_decimal(adv.get("AST_RATIO"))
                    adv_stats.oreb_pct = safe_decimal(adv.get("OREB_PCT"))
                    adv_stats.dreb_pct = safe_decimal(adv.get("DREB_PCT"))
                    adv_stats.reb_pct = safe_decimal(adv.get("REB_PCT"))
                    adv_stats.tm_tov_pct = safe_decimal(adv.get("TM_TOV_PCT"))

                # Upsert clutch stats
                clutch = clutch_by_player.get(player_id)
                if clutch:
                    clutch_stats = (
                        db.query(PlayerClutchStatsModel)
                        .filter(PlayerClutchStatsModel.player_id == player.id, PlayerClutchStatsModel.season == season)
                        .first()
                    )
                    if not clutch_stats:
                        clutch_stats = PlayerClutchStatsModel(player_id=player.id, season=season)
                        db.add(clutch_stats)

                    clutch_stats.games_played = safe_int(clutch.get("GP"))
                    clutch_stats.minutes = safe_decimal(clutch.get("MIN"))
                    clutch_stats.pts = safe_decimal(clutch.get("PTS"))
                    clutch_stats.fgm = safe_decimal(clutch.get("FGM"))
                    clutch_stats.fga = safe_decimal(clutch.get("FGA"))
                    clutch_stats.fg_pct = safe_decimal(clutch.get("FG_PCT"))
                    clutch_stats.fg3m = safe_decimal(clutch.get("FG3M"))
                    clutch_stats.fg3a = safe_decimal(clutch.get("FG3A"))
                    clutch_stats.fg3_pct = safe_decimal(clutch.get("FG3_PCT"))
                    clutch_stats.ftm = safe_decimal(clutch.get("FTM"))
                    clutch_stats.fta = safe_decimal(clutch.get("FTA"))
                    clutch_stats.ft_pct = safe_decimal(clutch.get("FT_PCT"))
                    clutch_stats.ast = safe_decimal(clutch.get("AST"))
                    clutch_stats.reb = safe_decimal(clutch.get("REB"))
                    clutch_stats.stl = safe_decimal(clutch.get("STL"))
                    clutch_stats.blk = safe_decimal(clutch.get("BLK"))
                    clutch_stats.tov = safe_decimal(clutch.get("TOV"))
                    clutch_stats.plus_minus = safe_decimal(clutch.get("PLUS_MINUS"))
                    clutch_stats.net_rating = safe_decimal(clutch.get("NET_RATING"))

                # Upsert defensive stats
                overall = overall_def_by_player.get(player_id)
                rim = rim_def_by_player.get(player_id)
                three_pt = three_pt_def_by_player.get(player_id)
                iso = iso_def_by_player.get(player_id)

                if overall or rim or three_pt or iso:
                    def_stats = (
                        db.query(PlayerDefensiveStatsModel)
                        .filter(PlayerDefensiveStatsModel.player_id == player.id, PlayerDefensiveStatsModel.season == season)
                        .first()
                    )
                    if not def_stats:
                        def_stats = PlayerDefensiveStatsModel(player_id=player.id, season=season)
                        db.add(def_stats)

                    if overall:
                        def_stats.overall_d_fgm = safe_decimal(overall.get("D_FGM"))
                        def_stats.overall_d_fga = safe_decimal(overall.get("D_FGA"))
                        def_stats.overall_d_fg_pct = safe_decimal(overall.get("D_FG_PCT"))
                        def_stats.overall_normal_fg_pct = safe_decimal(overall.get("NORMAL_FG_PCT"))
                        def_stats.overall_pct_plusminus = safe_decimal(overall.get("PCT_PLUSMINUS"))

                    if rim:
                        def_stats.rim_d_fgm = safe_decimal(rim.get("D_FGM"))
                        def_stats.rim_d_fga = safe_decimal(rim.get("D_FGA"))
                        def_stats.rim_d_fg_pct = safe_decimal(rim.get("D_FG_PCT"))
                        def_stats.rim_normal_fg_pct = safe_decimal(rim.get("NORMAL_FG_PCT"))
                        def_stats.rim_pct_plusminus = safe_decimal(rim.get("PCT_PLUSMINUS"))

                    if three_pt:
                        def_stats.three_pt_d_fgm = safe_decimal(three_pt.get("D_FGM"))
                        def_stats.three_pt_d_fga = safe_decimal(three_pt.get("D_FGA"))
                        def_stats.three_pt_d_fg_pct = safe_decimal(three_pt.get("D_FG_PCT"))
                        def_stats.three_pt_normal_fg_pct = safe_decimal(three_pt.get("NORMAL_FG_PCT"))
                        def_stats.three_pt_pct_plusminus = safe_decimal(three_pt.get("PCT_PLUSMINUS"))

                    if iso:
                        def_stats.iso_poss = safe_int(iso.get("POSS"))
                        def_stats.iso_pts = safe_int(iso.get("PTS"))
                        def_stats.iso_fgm = safe_int(iso.get("FGM"))
                        def_stats.iso_fga = safe_int(iso.get("FGA"))
                        def_stats.iso_ppp = safe_decimal(iso.get("PPP"))
                        def_stats.iso_fg_pct = safe_decimal(iso.get("FG_PCT"))
                        def_stats.iso_percentile = safe_decimal(iso.get("PERCENTILE"))

                processed += 1

            except Exception as e:
                logger.error("Error processing player %d: %s", player_id, e)
                errors += 1

        # Store shot zone data
        league_avg_lookup = {}
        if isinstance(league_averages, list):
            for zone_data in league_averages:
                zone_name = zone_data.get("ZONE_NAME") or zone_data.get("SHOT_ZONE_BASIC")
                if zone_name:
                    league_avg_lookup[zone_name] = safe_decimal(zone_data.get("FG_PCT"))
        elif isinstance(league_averages, dict):
            league_avg_lookup = {k: safe_decimal(v) for k, v in league_averages.items()}

        for shot_row in shot_data:
            try:
                pid = shot_row.get("PLAYER_ID")
                if not pid:
                    continue
                player = db.query(Player).filter(Player.nba_id == pid).first()
                if not player:
                    continue

                zone_name = shot_row.get("ZONE_NAME") or shot_row.get("SHOT_ZONE_BASIC", "Unknown")
                fgm = safe_decimal(shot_row.get("FGM"))
                fga = safe_decimal(shot_row.get("FGA"))
                fg_pct = safe_decimal(shot_row.get("FG_PCT"))
                total_fga = safe_decimal(shot_row.get("TOTAL_FGA"))
                freq = None
                if total_fga and total_fga > 0 and fga is not None:
                    freq = fga / total_fga
                league_avg = league_avg_lookup.get(zone_name)

                existing = (
                    db.query(PlayerShotZonesModel)
                    .filter(
                        PlayerShotZonesModel.player_id == player.id,
                        PlayerShotZonesModel.season == season,
                        PlayerShotZonesModel.zone == zone_name,
                    )
                    .first()
                )
                if not existing:
                    existing = PlayerShotZonesModel(player_id=player.id, season=season, zone=zone_name)
                    db.add(existing)

                existing.fgm = fgm
                existing.fga = fga
                existing.fg_pct = fg_pct
                existing.freq = freq
                existing.league_avg = league_avg

            except Exception as e:
                logger.error("Error processing shot zone data: %s", e)
                errors += 1

        db.commit()

        logger.info("Advanced data refresh completed: %d processed, %d errors", processed, errors)
        return {"status": "success", "processed": processed, "errors": errors, "season": season}

    except Exception as e:
        logger.exception("Advanced data refresh failed: %s", e)
        db.rollback()
        raise

    finally:
        db.close()


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
)
def refresh_phase2_data(self, season: str | None = None) -> dict:
    """Fetch Phase 2 data: shooting tracking, computed metrics, and career stats.

    Args:
        season: NBA season string. Defaults to current season.

    Returns:
        dict with status and counts
    """
    from decimal import Decimal

    from app.models import Player
    from app.models.advanced_stats import PlayerAdvancedStats
    from app.models.career_stats import PlayerCareerStats as PlayerCareerStatsModel
    from app.models.clutch_stats import PlayerClutchStats as PlayerClutchStatsModel
    from app.models.computed_advanced import PlayerComputedAdvanced
    from app.models.defensive_matchups import PlayerDefensiveStats as PlayerDefensiveStatsModel
    from app.models.season_play_type_stats import SeasonPlayTypeStats
    from app.models.season_stats import SeasonStats
    from app.models.shooting_tracking import PlayerShootingTracking
    from app.services.nba_data import NBADataService
    from app.services.rate_limiter import CircuitBreakerError, RateLimitError

    season = season or get_current_season()
    logger.info("Starting Phase 2 data refresh for season %s", season)

    db = SessionLocal()
    try:
        service = NBADataService(bypass_cache=True)

        # Import the fetch functions from the script
        from scripts.fetch_phase2_data import (
            compute_and_store_metrics,
            fetch_and_store_career_stats,
            fetch_and_store_shooting_tracking,
        )

        # Part A: Shooting tracking
        part_a = fetch_and_store_shooting_tracking(season, db, service)
        logger.info("Part A result: %s", part_a)

        # Part B: Computed metrics
        part_b = compute_and_store_metrics(season, db, service)
        logger.info("Part B result: %s", part_b)

        # Part C: Career stats (limited to top 50 for task runtime)
        part_c = fetch_and_store_career_stats(db, service, career_limit=50)
        logger.info("Part C result: %s", part_c)

        processed = (
            part_a.get("processed", 0)
            + part_b.get("stored", 0)
            + part_c.get("processed", 0)
        )
        errors = (
            part_a.get("errors", 0)
            + part_b.get("errors", 0)
            + part_c.get("errors", 0)
        )

        logger.info(
            "Phase 2 data refresh completed: %d processed, %d errors",
            processed,
            errors,
        )
        return {
            "status": "success",
            "processed": processed,
            "errors": errors,
            "season": season,
        }

    except Exception as e:
        logger.exception("Phase 2 data refresh failed: %s", e)
        db.rollback()
        raise

    finally:
        db.close()


@celery_app.task(bind=True)
def daily_data_refresh(self, season: str | None = None) -> dict:
    """Orchestrate the full daily data refresh.

    Runs tracking data first, then impact, play type, and advanced data in parallel,
    followed by metric recalculation.

    Args:
        season: NBA season string. Defaults to current season.

    Returns:
        dict with overall status
    """
    from app.tasks.metrics import recalculate_metrics

    season = season or get_current_season()
    logger.info("Starting daily data refresh for season %s", season)

    # Chain: tracking first, then Phase 1 group, then Phase 2 (depends on Phase 1), then recalculate
    workflow = chain(
        refresh_tracking_data.s(season),
        group(
            refresh_impact_data.s(season),
            refresh_play_type_data.s(season),
            refresh_advanced_data.s(season),
        ),
        refresh_phase2_data.si(season),  # si() ignores previous result; depends on Phase 1 data
        recalculate_metrics.si(season),
    )

    result = workflow.apply_async()
    logger.info("Daily data refresh workflow started: %s", result.id)

    return {
        "status": "started",
        "workflow_id": result.id,
        "season": season,
    }
