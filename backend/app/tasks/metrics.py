"""Celery task for recalculating player metrics.

This task recalculates all derived metrics (offensive, defensive, overall)
and updates percentiles. It runs after the daily data refresh completes
and can be triggered manually for formula updates.
"""

import logging
import time
from decimal import Decimal

from app.core.celery_app import celery_app
from app.db.session import SessionLocal

logger = logging.getLogger(__name__)


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
)
def recalculate_metrics(self, season: str) -> dict:
    """Recalculate all player metrics for a given season.

    This task is idempotent - running it multiple times produces the same results.
    It recalculates:
    - Offensive metrics (points per touch, assist rate, etc.)
    - Defensive metrics (deflections, contests, etc.)
    - Overall metrics (weighted combination)
    - League percentiles for all metrics

    Args:
        season: NBA season string (e.g., "2024-25")

    Returns:
        dict with status, timing, and player counts
    """
    from app.models import SeasonStats
    from app.services.metrics import MetricsCalculator

    start_time = time.time()
    logger.info("Starting metric recalculation for season %s", season)

    db = SessionLocal()
    try:
        # Fetch all season stats
        all_stats = db.query(SeasonStats).filter(SeasonStats.season == season).all()

        if not all_stats:
            logger.warning("No stats found for season %s", season)
            return {
                "status": "warning",
                "message": f"No stats found for season {season}",
                "season": season,
            }

        logger.info("Found %d players to recalculate", len(all_stats))

        # Calculate league average touches for normalization
        total_touches = sum(s.total_touches or 0 for s in all_stats)
        player_count = len([s for s in all_stats if (s.total_touches or 0) > 0])

        if player_count == 0:
            logger.warning("No players with touches found")
            return {
                "status": "warning",
                "message": "No players with touch data found",
                "season": season,
            }

        league_avg_touches = Decimal(total_touches) / Decimal(player_count)
        logger.info("League average touches: %.1f", league_avg_touches)

        # Initialize calculator with current league average
        calculator = MetricsCalculator(league_avg_touches)

        # Recalculate metrics for each player
        updated = 0
        errors = 0

        for stats in all_stats:
            try:
                touches = stats.total_touches or 0
                if touches == 0:
                    continue

                # Calculate offensive rates
                assist_rate = Decimal(stats.total_assists or 0) / Decimal(touches)
                turnover_rate = Decimal(stats.total_turnovers or 0) / Decimal(touches)
                ft_rate = Decimal(stats.total_fta or 0) / Decimal(touches)
                points_per_touch = stats.avg_points_per_touch or Decimal(0)

                # Calculate offensive metric
                offensive_metric = calculator.calculate_offensive_metric(
                    points_per_touch=points_per_touch,
                    assist_rate=assist_rate,
                    turnover_rate=turnover_rate,
                    ft_rate=ft_rate,
                    total_touches=touches,
                )

                # Calculate defensive rates
                est_possessions = stats.estimated_possessions or 0
                if est_possessions > 0:
                    deflections_per_100 = (
                        Decimal((stats.total_deflections or 0) * 100) / Decimal(est_possessions)
                    )
                    contests_per_100 = (
                        Decimal((stats.total_contested_shots or 0) * 100) / Decimal(est_possessions)
                    )
                    charges_per_100 = (
                        Decimal((stats.total_charges_drawn or 0) * 100) / Decimal(est_possessions)
                    )
                    loose_balls_per_100 = (
                        Decimal((stats.total_loose_balls_recovered or 0) * 100) / Decimal(est_possessions)
                    )
                    steals_per_100 = (
                        Decimal((stats.total_steals or 0) * 100) / Decimal(est_possessions)
                    )
                else:
                    deflections_per_100 = Decimal(0)
                    contests_per_100 = Decimal(0)
                    charges_per_100 = Decimal(0)
                    loose_balls_per_100 = Decimal(0)
                    steals_per_100 = Decimal(0)

                # Calculate defensive metric
                defensive_metric = calculator.calculate_defensive_metric(
                    deflections_per_100=deflections_per_100,
                    contests_per_100=contests_per_100,
                    steals_per_100=steals_per_100,
                    charges_per_100=charges_per_100,
                    loose_balls_per_100=loose_balls_per_100,
                    total_possessions=est_possessions,
                )

                # Calculate overall metric (weighted: 60% offensive, 40% defensive)
                if offensive_metric > 0 or defensive_metric > 0:
                    overall_metric = (
                        offensive_metric * Decimal("0.6") + defensive_metric * Decimal("0.4")
                    )
                else:
                    overall_metric = Decimal(0)

                # Update stats
                stats.offensive_metric = offensive_metric
                stats.defensive_metric = defensive_metric
                stats.overall_metric = overall_metric

                updated += 1

            except Exception as e:
                logger.error("Error recalculating metrics for player %d: %s", stats.player_id, e)
                errors += 1

        db.commit()
        metrics_time = time.time() - start_time
        logger.info("Metrics recalculated in %.2fs: %d updated, %d errors", metrics_time, updated, errors)

        # Recalculate percentiles
        percentile_start = time.time()
        percentile_result = _recalculate_percentiles(db, season)
        percentile_time = time.time() - percentile_start

        total_time = time.time() - start_time
        logger.info(
            "Metric recalculation completed in %.2fs (metrics: %.2fs, percentiles: %.2fs)",
            total_time, metrics_time, percentile_time
        )

        return {
            "status": "success",
            "season": season,
            "players_updated": updated,
            "errors": errors,
            "percentiles_calculated": percentile_result.get("count", 0),
            "timing": {
                "total_seconds": round(total_time, 2),
                "metrics_seconds": round(metrics_time, 2),
                "percentiles_seconds": round(percentile_time, 2),
            },
        }

    except Exception as e:
        logger.exception("Metric recalculation failed: %s", e)
        db.rollback()
        raise

    finally:
        db.close()


def _recalculate_percentiles(db, season: str) -> dict:
    """Recalculate league percentiles for all metrics.

    Args:
        db: Database session
        season: NBA season string

    Returns:
        dict with count of players processed
    """
    from app.models import SeasonStats

    # Get all stats with valid metrics
    stats = (
        db.query(SeasonStats)
        .filter(SeasonStats.season == season)
        .filter(SeasonStats.offensive_metric > 0)
        .all()
    )

    if not stats:
        logger.warning("No stats with metrics found for percentile calculation")
        return {"count": 0}

    # Sort and assign offensive percentiles
    off_sorted = sorted(stats, key=lambda x: x.offensive_metric or 0)
    for i, stat in enumerate(off_sorted):
        stat.offensive_percentile = int((i / len(off_sorted)) * 100)

    # Sort and assign defensive percentiles
    def_sorted = sorted(stats, key=lambda x: x.defensive_metric or 0)
    for i, stat in enumerate(def_sorted):
        stat.defensive_percentile = int((i / len(def_sorted)) * 100)

    db.commit()
    logger.info("Percentiles recalculated for %d players", len(stats))

    return {"count": len(stats)}


@celery_app.task(bind=True)
def recalculate_all_metrics(self, season: str | None = None) -> dict:
    """Recalculate metrics and impact percentiles for a season.

    This is a convenience task that recalculates all metrics including
    impact percentiles. Use this for complete metric refresh.

    Args:
        season: NBA season string. Defaults to current season.

    Returns:
        dict with combined results
    """
    from app.tasks.data_refresh import get_current_season

    season = season or get_current_season()
    logger.info("Starting full metric recalculation for season %s", season)

    # Recalculate base metrics
    base_result = recalculate_metrics.delay(season)

    # Also recalculate impact percentiles
    impact_result = recalculate_impact_percentiles.delay(season)

    return {
        "status": "started",
        "season": season,
        "base_metrics_task_id": base_result.id,
        "impact_percentiles_task_id": impact_result.id,
    }


@celery_app.task(
    bind=True,
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 2},
)
def recalculate_impact_percentiles(self, season: str) -> dict:
    """Recalculate impact percentiles for a season.

    Args:
        season: NBA season string

    Returns:
        dict with status and count
    """
    from app.models import ContextualizedImpact

    logger.info("Recalculating impact percentiles for season %s", season)

    db = SessionLocal()
    try:
        impacts = (
            db.query(ContextualizedImpact)
            .filter(
                ContextualizedImpact.season == season,
                ContextualizedImpact.contextualized_net_impact.isnot(None),
            )
            .all()
        )

        if not impacts:
            logger.warning("No impact data found for season %s", season)
            return {"status": "warning", "message": "No impact data found", "count": 0}

        # Net impact percentiles
        net_sorted = sorted(impacts, key=lambda x: x.contextualized_net_impact or 0)
        for i, impact in enumerate(net_sorted):
            impact.impact_percentile = int((i / len(net_sorted)) * 100)

        # Offensive impact percentiles
        off_sorted = sorted(impacts, key=lambda x: x.contextualized_off_impact or 0)
        for i, impact in enumerate(off_sorted):
            impact.offensive_impact_percentile = int((i / len(off_sorted)) * 100)

        # Defensive impact percentiles (lower is better)
        def_sorted = sorted(impacts, key=lambda x: x.contextualized_def_impact or 0)
        for i, impact in enumerate(def_sorted):
            impact.defensive_impact_percentile = int(((len(def_sorted) - i - 1) / len(def_sorted)) * 100)

        db.commit()
        logger.info("Impact percentiles recalculated for %d players", len(impacts))

        return {"status": "success", "season": season, "count": len(impacts)}

    except Exception as e:
        logger.exception("Impact percentile recalculation failed: %s", e)
        db.rollback()
        raise

    finally:
        db.close()
