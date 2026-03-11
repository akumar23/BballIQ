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


@celery_app.task(bind=True)
def daily_data_refresh(self, season: str | None = None) -> dict:
    """Orchestrate the full daily data refresh.

    Runs tracking data first, then impact and play type data in parallel.

    Args:
        season: NBA season string. Defaults to current season.

    Returns:
        dict with overall status
    """
    season = season or get_current_season()
    logger.info("Starting daily data refresh for season %s", season)

    # Chain: tracking first, then group of impact + play_type
    workflow = chain(
        refresh_tracking_data.s(season),
        group(
            refresh_impact_data.s(season),
            refresh_play_type_data.s(season),
        ),
    )

    result = workflow.apply_async()
    logger.info("Daily data refresh workflow started: %s", result.id)

    return {
        "status": "started",
        "workflow_id": result.id,
        "season": season,
    }
