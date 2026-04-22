"""Celery tasks for daily NBA data refresh.

These tasks wrap the existing fetch scripts to run as scheduled background jobs.
"""

import logging

import requests
import sqlalchemy.exc
from celery import chain, group

from app.core.celery_app import celery_app
from app.core.season import get_current_season
from app.db.session import SessionLocal
from app.services.rate_limiter import CircuitBreakerError, RateLimitError

logger = logging.getLogger(__name__)

__all__ = [
    "get_current_season",
    "refresh_tracking_data",
    "refresh_impact_data",
    "refresh_play_type_data",
    "refresh_advanced_data",
    "refresh_phase2_data",
    "daily_data_refresh",
    "BATCH_COMMIT_SIZE",
    "ERROR_THRESHOLD_RATIO",
]


# Batch size for intra-task commits: commit every N players so a late failure
# doesn't roll back all upstream work. Also serves as the savepoint cadence.
BATCH_COMMIT_SIZE = 50

# Maximum per-task allowed error rate before the task is considered failed.
# Surfaces systemic issues (10% of players failing is not "success").
ERROR_THRESHOLD_RATIO = 0.1

# Exceptions worth retrying: transient network / upstream / DB connection
# issues. Programming errors (KeyError, TypeError, ValueError, ...) are NOT
# in this list — those should fail fast so they can be fixed.
_RETRY_EXCEPTIONS: tuple[type[BaseException], ...] = (
    CircuitBreakerError,
    RateLimitError,
    requests.RequestException,
    sqlalchemy.exc.OperationalError,
    sqlalchemy.exc.InterfaceError,
)


def _update_set(values: dict[str, object], *exclude: str) -> dict[str, object]:
    """Return ``values`` with the given key columns removed.

    Used to build the ``set_`` argument for ``ON CONFLICT DO UPDATE`` so the
    conflict-target columns are not rewritten with identical values.
    """
    skip = set(exclude)
    return {k: v for k, v in values.items() if k not in skip}


def _finalize_task_status(
    *,
    task_name: str,
    processed: int,
    errors: int,
    total: int,
    season: str,
    extra: dict[str, object] | None = None,
) -> dict[str, object]:
    """Build the task's return payload and raise when the error rate is too high.

    Args:
        task_name: Human-readable task identifier (used in the raised error).
        processed: Successfully processed rows.
        errors: Rows that failed inside the per-row savepoint.
        total: Total rows attempted (``processed + errors`` in normal cases;
            callers may pass the full input size when they skip rows).
        season: NBA season string, included in the returned payload.
        extra: Optional task-specific fields merged into the payload.

    Returns:
        A status dict with ``status``, ``total``, ``processed``, ``errors``,
        ``error_rate`` and ``season`` keys.

    Raises:
        RuntimeError: If ``errors / max(total, 1) > ERROR_THRESHOLD_RATIO``.
    """
    denom = max(total, 1)
    error_rate = errors / denom
    payload: dict[str, object] = {
        "status": "degraded" if errors > 0 else "success",
        "total": total,
        "processed": processed,
        "errors": errors,
        "error_rate": error_rate,
        "season": season,
    }
    if extra:
        payload.update(extra)

    if error_rate > ERROR_THRESHOLD_RATIO:
        raise RuntimeError(
            f"{errors}/{total} players failed in {task_name} "
            f"(error_rate={error_rate:.2%}, threshold={ERROR_THRESHOLD_RATIO:.0%})"
        )
    return payload


@celery_app.task(
    bind=True,
    autoretry_for=_RETRY_EXCEPTIONS,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
)
def refresh_tracking_data(self, season: str | None = None) -> dict[str, object]:
    """Fetch tracking data and store in database.

    This is the main data fetch that populates player stats.
    Must run before impact and play type tasks.

    Args:
        season: NBA season string (e.g., "2024-25"). Defaults to current season.

    Returns:
        dict with status, totals, errors, error_rate and season.
    """
    # Import here to avoid circular imports and ensure fresh module state
    from decimal import Decimal

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models import Per75Stats, Player, SeasonStats
    from app.services.metrics import MetricsCalculator
    from app.services.nba_data import NBADataService
    from app.services.per_75_calculator import per_75_calculator

    season = season or get_current_season()
    logger.info("Starting tracking data refresh for season %s", season)

    db = SessionLocal()
    try:
        service = NBADataService(bypass_cache=True)

        # Fetch tracking data
        try:
            tracking_data = service.fetch_all_tracking_data(season)
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch tracking data: %s", e, exc_info=True)
            raise self.retry(exc=e) from e

        if not tracking_data:
            logger.error("No tracking data fetched for season %s", season)
            return {"status": "error", "message": "No tracking data fetched"}

        logger.info("Fetched data for %d players", len(tracking_data))

        # Calculate league averages
        total_touches = sum(p.touches for p in tracking_data.values())
        league_avg_touches = Decimal(total_touches) / Decimal(len(tracking_data))
        calculator = MetricsCalculator(league_avg_touches)

        total = len(tracking_data)
        processed = 0
        errors = 0
        since_last_commit = 0

        for player_id, data in tracking_data.items():
            try:
                with db.begin_nested():
                    # Upsert player (nba_id is unique)
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
                        poss_dec = Decimal(est_def_possessions)
                        total_contests = data.contested_shots_2pt + data.contested_shots_3pt
                        deflections_per_100 = Decimal(data.deflections * 100) / poss_dec
                        contests_per_100 = Decimal(total_contests * 100) / poss_dec
                        charges_per_100 = Decimal(data.charges_drawn * 100) / poss_dec
                        loose_balls_per_100 = (
                            Decimal(data.loose_balls_recovered * 100) / poss_dec
                        )
                    else:
                        deflections_per_100 = Decimal(0)
                        contests_per_100 = Decimal(0)
                        charges_per_100 = Decimal(0)
                        loose_balls_per_100 = Decimal(0)

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

                    # Upsert season_stats via ON CONFLICT — idempotent on retry
                    season_stats_values = {
                        "player_id": player.id,
                        "season": season,
                        "games_played": data.games_played,
                        "total_minutes": data.minutes,
                        "total_points": data.points,
                        "total_assists": data.assists,
                        "total_rebounds": data.rebounds,
                        "total_offensive_rebounds": data.offensive_rebounds,
                        "total_defensive_rebounds": data.defensive_rebounds,
                        "total_steals": data.steals,
                        "total_blocks": data.blocks,
                        "total_turnovers": data.turnovers,
                        "total_fgm": data.fgm,
                        "total_fga": data.fga,
                        "total_fg3m": data.fg3m,
                        "total_fg3a": data.fg3a,
                        "total_ftm": data.ftm,
                        "total_fta": data.fta,
                        "total_plus_minus": data.plus_minus,
                        "total_touches": data.touches,
                        "total_front_court_touches": data.front_court_touches,
                        "total_time_of_possession": data.time_of_possession,
                        "avg_points_per_touch": data.points_per_touch,
                        "total_deflections": data.deflections,
                        "total_contested_shots": (
                            data.contested_shots_2pt + data.contested_shots_3pt
                        ),
                        "total_contested_shots_2pt": data.contested_shots_2pt,
                        "total_contested_shots_3pt": data.contested_shots_3pt,
                        "total_charges_drawn": data.charges_drawn,
                        "total_loose_balls_recovered": data.loose_balls_recovered,
                        "total_box_outs": data.box_outs,
                        "total_box_outs_off": data.box_outs_off,
                        "total_box_outs_def": data.box_outs_def,
                        "total_screen_assists": data.screen_assists,
                        "total_screen_assist_pts": data.screen_assist_pts,
                        "estimated_possessions": est_def_possessions,
                        "offensive_metric": offensive_metric,
                        "defensive_metric": defensive_metric,
                        "overall_metric": overall_metric,
                    }
                    update_set = _update_set(season_stats_values, "player_id", "season")
                    stmt = (
                        pg_insert(SeasonStats)
                        .values(**season_stats_values)
                        .on_conflict_do_update(
                            index_elements=["player_id", "season"],
                            set_=update_set,
                        )
                        .returning(SeasonStats.id)
                    )
                    season_stats_id = db.execute(stmt).scalar_one()

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

                    per_75_values = {
                        "season_stats_id": season_stats_id,
                        "season": season,
                        "pts_per_75": per_75_data.pts_per_75,
                        "fgm_per_75": per_75_data.fgm_per_75,
                        "fga_per_75": per_75_data.fga_per_75,
                        "fg3m_per_75": per_75_data.fg3m_per_75,
                        "fg3a_per_75": per_75_data.fg3a_per_75,
                        "ftm_per_75": per_75_data.ftm_per_75,
                        "fta_per_75": per_75_data.fta_per_75,
                        "ast_per_75": per_75_data.ast_per_75,
                        "tov_per_75": per_75_data.tov_per_75,
                        "reb_per_75": per_75_data.reb_per_75,
                        "oreb_per_75": per_75_data.oreb_per_75,
                        "dreb_per_75": per_75_data.dreb_per_75,
                        "stl_per_75": per_75_data.stl_per_75,
                        "blk_per_75": per_75_data.blk_per_75,
                        "deflections_per_75": per_75_data.deflections_per_75,
                        "contested_shots_per_75": per_75_data.contested_shots_per_75,
                        "contested_2pt_per_75": per_75_data.contested_2pt_per_75,
                        "contested_3pt_per_75": per_75_data.contested_3pt_per_75,
                        "charges_drawn_per_75": per_75_data.charges_drawn_per_75,
                        "loose_balls_per_75": per_75_data.loose_balls_per_75,
                        "box_outs_per_75": per_75_data.box_outs_per_75,
                        "screen_assists_per_75": per_75_data.screen_assists_per_75,
                        "touches_per_75": per_75_data.touches_per_75,
                        "front_court_touches_per_75": per_75_data.front_court_touches_per_75,
                        "possessions_used": per_75_data.possessions_used,
                    }
                    per_75_update = _update_set(per_75_values, "season_stats_id")
                    db.execute(
                        pg_insert(Per75Stats)
                        .values(**per_75_values)
                        .on_conflict_do_update(
                            index_elements=["season_stats_id"],
                            set_=per_75_update,
                        )
                    )

                processed += 1
                since_last_commit += 1
                if since_last_commit >= BATCH_COMMIT_SIZE:
                    db.commit()
                    since_last_commit = 0

            except _RETRY_EXCEPTIONS:
                # Transient / DB-level failure: don't swallow it — let Celery retry
                # the whole task so we don't leave a half-written state behind.
                db.rollback()
                raise
            except Exception as e:
                logger.error(
                    "Error processing player %d: %s", player_id, e, exc_info=True
                )
                errors += 1
                # Nested savepoint auto-rolled back via context manager on exception,
                # but keep the outer session clean.

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

        logger.info(
            "Tracking data refresh completed: %d/%d processed, %d errors",
            processed,
            total,
            errors,
        )
        return _finalize_task_status(
            task_name="refresh_tracking_data",
            processed=processed,
            errors=errors,
            total=total,
            season=season,
        )

    except RuntimeError:
        # Threshold-exceeded failure — already logged, allow to surface to Celery.
        db.rollback()
        raise
    except Exception as e:
        logger.exception("Tracking data refresh failed: %s", e)
        db.rollback()
        raise

    finally:
        db.close()


@celery_app.task(
    bind=True,
    autoretry_for=_RETRY_EXCEPTIONS,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
)
def refresh_impact_data(self, season: str | None = None) -> dict[str, object]:
    """Fetch impact data and store in database.

    Args:
        season: NBA season string. Defaults to current season.

    Returns:
        dict with status, totals, errors, error_rate and season.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models import ContextualizedImpact, Player, PlayerOnOffStats
    from app.services.impact_calculator import ImpactCalculator
    from app.services.nba_data import NBADataService

    season = season or get_current_season()
    logger.info("Starting impact data refresh for season %s", season)

    db = SessionLocal()
    try:
        service = NBADataService(bypass_cache=True)

        # Fetch lineup data
        try:
            lineup_data = service.fetch_lineup_data(season)
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch lineup data: %s", e, exc_info=True)
            raise self.retry(exc=e) from e

        # Fetch on/off data
        try:
            on_off_data = service.get_all_on_off_stats(season)
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch on/off data: %s", e, exc_info=True)
            raise self.retry(exc=e) from e

        # Calculate impact
        calculator = ImpactCalculator(lineup_data, on_off_data)
        impacts = calculator.calculate_all_impacts()

        total = len(on_off_data)
        processed = 0
        errors = 0
        since_last_commit = 0

        for player_id, on_off in on_off_data.items():
            try:
                with db.begin_nested():
                    player = db.query(Player).filter(Player.nba_id == player_id).first()
                    if not player:
                        continue

                    on_off_values = {
                        "player_id": player.id,
                        "season": season,
                        "on_court_minutes": on_off.on_court_min,
                        "on_court_plus_minus": on_off.on_court_plus_minus,
                        "on_court_off_rating": on_off.on_court_off_rating,
                        "on_court_def_rating": on_off.on_court_def_rating,
                        "on_court_net_rating": on_off.on_court_net_rating,
                        "off_court_minutes": on_off.off_court_min,
                        "off_court_plus_minus": on_off.off_court_plus_minus,
                        "off_court_off_rating": on_off.off_court_off_rating,
                        "off_court_def_rating": on_off.off_court_def_rating,
                        "off_court_net_rating": on_off.off_court_net_rating,
                        "plus_minus_diff": on_off.plus_minus_diff,
                        "off_rating_diff": on_off.off_rating_diff,
                        "def_rating_diff": on_off.def_rating_diff,
                        "net_rating_diff": on_off.net_rating_diff,
                    }
                    on_off_update = _update_set(on_off_values, "player_id", "season")
                    db.execute(
                        pg_insert(PlayerOnOffStats)
                        .values(**on_off_values)
                        .on_conflict_do_update(
                            index_elements=["player_id", "season"],
                            set_=on_off_update,
                        )
                    )

                    impact_data = impacts.get(player_id)
                    if impact_data:
                        impact_values = {
                            "player_id": player.id,
                            "season": season,
                            "raw_net_rating_diff": impact_data.raw_net_rating_diff,
                            "raw_off_rating_diff": impact_data.raw_off_rating_diff,
                            "raw_def_rating_diff": impact_data.raw_def_rating_diff,
                            "avg_teammate_net_rating": impact_data.avg_teammate_net_rating,
                            "teammate_adjustment": impact_data.teammate_adjustment,
                            "pct_minutes_vs_starters": impact_data.pct_minutes_vs_starters,
                            "opponent_quality_factor": impact_data.opponent_quality_factor,
                            "total_on_court_minutes": impact_data.total_on_court_minutes,
                            "reliability_factor": impact_data.reliability_factor,
                            "contextualized_off_impact": impact_data.contextualized_off_impact,
                            "contextualized_def_impact": impact_data.contextualized_def_impact,
                            "contextualized_net_impact": impact_data.contextualized_net_impact,
                        }
                        impact_update = _update_set(impact_values, "player_id", "season")
                        db.execute(
                            pg_insert(ContextualizedImpact)
                            .values(**impact_values)
                            .on_conflict_do_update(
                                index_elements=["player_id", "season"],
                                set_=impact_update,
                            )
                        )

                processed += 1
                since_last_commit += 1
                if since_last_commit >= BATCH_COMMIT_SIZE:
                    db.commit()
                    since_last_commit = 0

            except _RETRY_EXCEPTIONS:
                db.rollback()
                raise
            except Exception as e:
                logger.error(
                    "Error processing player %d: %s", player_id, e, exc_info=True
                )
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

        logger.info(
            "Impact data refresh completed: %d/%d processed, %d errors",
            processed,
            total,
            errors,
        )
        return _finalize_task_status(
            task_name="refresh_impact_data",
            processed=processed,
            errors=errors,
            total=total,
            season=season,
        )

    except RuntimeError:
        db.rollback()
        raise
    except Exception as e:
        logger.exception("Impact data refresh failed: %s", e)
        db.rollback()
        raise

    finally:
        db.close()


@celery_app.task(
    bind=True,
    autoretry_for=_RETRY_EXCEPTIONS,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
)
def refresh_play_type_data(self, season: str | None = None) -> dict[str, object]:
    """Fetch play type data and store in database.

    Args:
        season: NBA season string. Defaults to current season.

    Returns:
        dict with status, totals, errors, error_rate and season.
    """
    from decimal import Decimal

    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models import Player, SeasonPlayTypeStats
    from app.services.nba_data import PLAY_TYPE_MAPPING, NBADataService

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
            logger.error("Failed to fetch play type data: %s", e, exc_info=True)
            raise self.retry(exc=e) from e

        total = len(play_type_data)
        processed = 0
        errors = 0
        since_last_commit = 0

        for player_id, data in play_type_data.items():
            try:
                with db.begin_nested():
                    player = db.query(Player).filter(Player.nba_id == player_id).first()
                    if not player:
                        continue

                    values: dict[str, object] = {
                        "player_id": player.id,
                        "season": season,
                        "total_poss": data.total_poss,
                    }

                    for field_name in PLAY_TYPE_MAPPING.keys():
                        metrics = getattr(data, field_name)
                        if metrics is None:
                            continue

                        values[f"{field_name}_poss"] = metrics.possessions
                        values[f"{field_name}_pts"] = metrics.points
                        values[f"{field_name}_fgm"] = metrics.fgm
                        values[f"{field_name}_fga"] = metrics.fga

                        ppp = fg_pct = freq = None
                        poss = metrics.possessions
                        if poss and poss > 0 and metrics.points is not None:
                            ppp = Decimal(str(metrics.points)) / Decimal(str(poss))
                        if metrics.fga and metrics.fga > 0 and metrics.fgm is not None:
                            fg_pct = Decimal(str(metrics.fgm)) / Decimal(str(metrics.fga))
                        if data.total_poss and data.total_poss > 0 and poss:
                            freq = Decimal(str(poss)) / Decimal(str(data.total_poss))

                        values[f"{field_name}_ppp"] = ppp
                        values[f"{field_name}_fg_pct"] = fg_pct
                        values[f"{field_name}_freq"] = freq

                        if field_name == "spot_up" and metrics.fg3m is not None:
                            values["spot_up_fg3m"] = metrics.fg3m
                            values["spot_up_fg3a"] = metrics.fg3a
                            if metrics.fg3a and metrics.fg3a > 0:
                                values["spot_up_fg3_pct"] = (
                                    Decimal(str(metrics.fg3m)) / Decimal(str(metrics.fg3a))
                                )

                    update_set = _update_set(values, "player_id", "season")
                    db.execute(
                        pg_insert(SeasonPlayTypeStats)
                        .values(**values)
                        .on_conflict_do_update(
                            index_elements=["player_id", "season"],
                            set_=update_set,
                        )
                    )

                processed += 1
                since_last_commit += 1
                if since_last_commit >= BATCH_COMMIT_SIZE:
                    db.commit()
                    since_last_commit = 0

            except _RETRY_EXCEPTIONS:
                db.rollback()
                raise
            except Exception as e:
                logger.error(
                    "Error processing player %d: %s", player_id, e, exc_info=True
                )
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

        logger.info(
            "Play type data refresh completed: %d/%d processed, %d errors",
            processed,
            total,
            errors,
        )
        return _finalize_task_status(
            task_name="refresh_play_type_data",
            processed=processed,
            errors=errors,
            total=total,
            season=season,
        )

    except RuntimeError:
        db.rollback()
        raise
    except Exception as e:
        logger.exception("Play type data refresh failed: %s", e)
        db.rollback()
        raise

    finally:
        db.close()


@celery_app.task(
    bind=True,
    autoretry_for=_RETRY_EXCEPTIONS,
    retry_backoff=True,
    retry_backoff_max=300,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
)
def refresh_advanced_data(self, season: str | None = None) -> dict[str, object]:
    """Fetch advanced stats, shot zones, clutch, and defensive data.

    Args:
        season: NBA season string. Defaults to current season.

    Returns:
        dict with status, totals, errors, error_rate and season.
    """
    from sqlalchemy.dialects.postgresql import insert as pg_insert

    from app.models import Player
    from app.models.advanced_stats import PlayerAdvancedStats
    from app.models.clutch_stats import PlayerClutchStats as PlayerClutchStatsModel
    from app.models.defensive_matchups import PlayerDefensiveStats as PlayerDefensiveStatsModel
    from app.models.shot_zones import PlayerShotZones as PlayerShotZonesModel
    from app.services.nba_data import NBADataService
    from scripts.shared import safe_decimal, safe_int

    season = season or get_current_season()
    logger.info("Starting advanced data refresh for season %s", season)

    db = SessionLocal()
    try:
        service = NBADataService(bypass_cache=True)

        # Fetch advanced stats
        try:
            advanced_data = service.get_advanced_stats(season)
            advanced_by_player = {p["PLAYER_ID"]: p for p in advanced_data}
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch advanced stats: %s", e, exc_info=True)
            raise self.retry(exc=e) from e

        # Fetch clutch stats
        try:
            clutch_data = service.get_clutch_stats(season)
            clutch_by_player = {p["PLAYER_ID"]: p for p in clutch_data}
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch clutch stats: %s", e, exc_info=True)
            clutch_by_player = {}

        # Fetch defensive stats
        try:
            overall_defense = service.get_defensive_stats(season)
            overall_def_by_player = {p["CLOSE_DEF_PERSON_ID"]: p for p in overall_defense}
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch overall defensive stats: %s", e, exc_info=True)
            overall_def_by_player = {}

        try:
            rim_defense = service.get_rim_protection_stats(season)
            rim_def_by_player = {p["CLOSE_DEF_PERSON_ID"]: p for p in rim_defense}
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch rim protection stats: %s", e, exc_info=True)
            rim_def_by_player = {}

        try:
            three_pt_defense = service.get_three_point_defense_stats(season)
            three_pt_def_by_player = {p["CLOSE_DEF_PERSON_ID"]: p for p in three_pt_defense}
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch 3PT defensive stats: %s", e, exc_info=True)
            three_pt_def_by_player = {}

        try:
            iso_defense = service.get_defensive_play_type_stats("Isolation", season)
            iso_def_by_player = {p["PLAYER_ID"]: p for p in iso_defense}
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch isolation defense stats: %s", e, exc_info=True)
            iso_def_by_player = {}

        # Fetch shot zone data
        try:
            shot_data = service.get_shot_location_stats(season)
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch shot location stats: %s", e, exc_info=True)
            shot_data = []

        try:
            league_averages = service.get_league_shot_averages(season)
        except (CircuitBreakerError, RateLimitError) as e:
            logger.error("Failed to fetch league shot averages: %s", e, exc_info=True)
            league_averages = {}

        # Collect all player IDs
        all_player_ids: set[int] = set()
        all_player_ids.update(advanced_by_player.keys())
        all_player_ids.update(clutch_by_player.keys())
        all_player_ids.update(overall_def_by_player.keys())
        all_player_ids.update(rim_def_by_player.keys())
        all_player_ids.update(three_pt_def_by_player.keys())
        all_player_ids.update(iso_def_by_player.keys())

        total = len(all_player_ids)
        processed = 0
        errors = 0
        since_last_commit = 0

        for player_id in all_player_ids:
            try:
                with db.begin_nested():
                    player = db.query(Player).filter(Player.nba_id == player_id).first()
                    if not player:
                        continue

                    # Advanced stats upsert
                    adv = advanced_by_player.get(player_id)
                    if adv:
                        adv_values = {
                            "player_id": player.id,
                            "season": season,
                            "ts_pct": safe_decimal(adv.get("TS_PCT")),
                            "efg_pct": safe_decimal(adv.get("EFG_PCT")),
                            "usg_pct": safe_decimal(adv.get("USG_PCT")),
                            "off_rating": safe_decimal(adv.get("OFF_RATING")),
                            "def_rating": safe_decimal(adv.get("DEF_RATING")),
                            "net_rating": safe_decimal(adv.get("NET_RATING")),
                            "pace": safe_decimal(adv.get("PACE")),
                            "pie": safe_decimal(adv.get("PIE")),
                            "ast_pct": safe_decimal(adv.get("AST_PCT")),
                            "ast_to": safe_decimal(adv.get("AST_TO")),
                            "ast_ratio": safe_decimal(adv.get("AST_RATIO")),
                            "oreb_pct": safe_decimal(adv.get("OREB_PCT")),
                            "dreb_pct": safe_decimal(adv.get("DREB_PCT")),
                            "reb_pct": safe_decimal(adv.get("REB_PCT")),
                            "tm_tov_pct": safe_decimal(adv.get("TM_TOV_PCT")),
                            "e_off_rating": safe_decimal(adv.get("E_OFF_RATING")),
                            "e_def_rating": safe_decimal(adv.get("E_DEF_RATING")),
                            "e_net_rating": safe_decimal(adv.get("E_NET_RATING")),
                            "e_usg_pct": safe_decimal(adv.get("E_USG_PCT")),
                            "e_pace": safe_decimal(adv.get("E_PACE")),
                            "pace_per40": safe_decimal(adv.get("PACE_PER40")),
                            "poss": safe_int(adv.get("POSS")),
                        }
                        adv_update = _update_set(adv_values, "player_id", "season")
                        db.execute(
                            pg_insert(PlayerAdvancedStats)
                            .values(**adv_values)
                            .on_conflict_do_update(
                                index_elements=["player_id", "season"],
                                set_=adv_update,
                            )
                        )

                    # Clutch stats upsert
                    clutch = clutch_by_player.get(player_id)
                    if clutch:
                        clutch_values = {
                            "player_id": player.id,
                            "season": season,
                            "games_played": safe_int(clutch.get("GP")),
                            "minutes": safe_decimal(clutch.get("MIN")),
                            "pts": safe_decimal(clutch.get("PTS")),
                            "fgm": safe_decimal(clutch.get("FGM")),
                            "fga": safe_decimal(clutch.get("FGA")),
                            "fg_pct": safe_decimal(clutch.get("FG_PCT")),
                            "fg3m": safe_decimal(clutch.get("FG3M")),
                            "fg3a": safe_decimal(clutch.get("FG3A")),
                            "fg3_pct": safe_decimal(clutch.get("FG3_PCT")),
                            "ftm": safe_decimal(clutch.get("FTM")),
                            "fta": safe_decimal(clutch.get("FTA")),
                            "ft_pct": safe_decimal(clutch.get("FT_PCT")),
                            "ast": safe_decimal(clutch.get("AST")),
                            "reb": safe_decimal(clutch.get("REB")),
                            "stl": safe_decimal(clutch.get("STL")),
                            "blk": safe_decimal(clutch.get("BLK")),
                            "tov": safe_decimal(clutch.get("TOV")),
                            "plus_minus": safe_decimal(clutch.get("PLUS_MINUS")),
                            "net_rating": safe_decimal(clutch.get("NET_RATING")),
                        }
                        clutch_update = _update_set(clutch_values, "player_id", "season")
                        db.execute(
                            pg_insert(PlayerClutchStatsModel)
                            .values(**clutch_values)
                            .on_conflict_do_update(
                                index_elements=["player_id", "season"],
                                set_=clutch_update,
                            )
                        )

                    # Defensive stats upsert (merged overall/rim/three-pt/iso)
                    overall = overall_def_by_player.get(player_id)
                    rim = rim_def_by_player.get(player_id)
                    three_pt = three_pt_def_by_player.get(player_id)
                    iso = iso_def_by_player.get(player_id)

                    if overall or rim or three_pt or iso:
                        def_values: dict[str, object] = {
                            "player_id": player.id,
                            "season": season,
                        }
                        if overall:
                            def_values.update(
                                games_played=safe_int(overall.get("GP")),
                                age=safe_int(overall.get("AGE")),
                                overall_d_fgm=safe_decimal(overall.get("D_FGM")),
                                overall_d_fga=safe_decimal(overall.get("D_FGA")),
                                overall_d_fg_pct=safe_decimal(overall.get("D_FG_PCT")),
                                overall_normal_fg_pct=safe_decimal(overall.get("NORMAL_FG_PCT")),
                                overall_pct_plusminus=safe_decimal(overall.get("PCT_PLUSMINUS")),
                                overall_freq=safe_decimal(overall.get("FREQ")),
                            )
                        if rim:
                            def_values.update(
                                rim_d_fgm=safe_decimal(rim.get("D_FGM")),
                                rim_d_fga=safe_decimal(rim.get("D_FGA")),
                                rim_d_fg_pct=safe_decimal(rim.get("D_FG_PCT")),
                                rim_normal_fg_pct=safe_decimal(rim.get("NORMAL_FG_PCT")),
                                rim_pct_plusminus=safe_decimal(rim.get("PCT_PLUSMINUS")),
                                rim_freq=safe_decimal(rim.get("FREQ")),
                            )
                        if three_pt:
                            def_values.update(
                                three_pt_d_fgm=safe_decimal(three_pt.get("D_FGM")),
                                three_pt_d_fga=safe_decimal(three_pt.get("D_FGA")),
                                three_pt_d_fg_pct=safe_decimal(three_pt.get("D_FG_PCT")),
                                three_pt_normal_fg_pct=safe_decimal(three_pt.get("NORMAL_FG_PCT")),
                                three_pt_freq=safe_decimal(three_pt.get("FREQ")),
                                three_pt_pct_plusminus=safe_decimal(three_pt.get("PCT_PLUSMINUS")),
                            )
                        if iso:
                            def_values.update(
                                iso_poss=safe_int(iso.get("POSS")),
                                iso_pts=safe_int(iso.get("PTS")),
                                iso_fgm=safe_int(iso.get("FGM")),
                                iso_fga=safe_int(iso.get("FGA")),
                                iso_ppp=safe_decimal(iso.get("PPP")),
                                iso_fg_pct=safe_decimal(iso.get("FG_PCT")),
                                iso_percentile=safe_decimal(iso.get("PERCENTILE")),
                            )

                        def_update = _update_set(def_values, "player_id", "season")
                        db.execute(
                            pg_insert(PlayerDefensiveStatsModel)
                            .values(**def_values)
                            .on_conflict_do_update(
                                index_elements=["player_id", "season"],
                                set_=def_update,
                            )
                        )

                processed += 1
                since_last_commit += 1
                if since_last_commit >= BATCH_COMMIT_SIZE:
                    db.commit()
                    since_last_commit = 0

            except _RETRY_EXCEPTIONS:
                db.rollback()
                raise
            except Exception as e:
                logger.error(
                    "Error processing player %d: %s", player_id, e, exc_info=True
                )
                errors += 1

        # Commit any partial batch before starting the shot-zone phase.
        db.commit()

        # Store shot zone data (three-column composite key)
        league_avg_lookup: dict[str, object] = {}
        if isinstance(league_averages, list):
            for zone_data in league_averages:
                zone_name = zone_data.get("ZONE_NAME") or zone_data.get("SHOT_ZONE_BASIC")
                if zone_name:
                    league_avg_lookup[zone_name] = safe_decimal(zone_data.get("FG_PCT"))
        elif isinstance(league_averages, dict):
            league_avg_lookup = {k: safe_decimal(v) for k, v in league_averages.items()}

        shot_total = len(shot_data)
        shot_processed = 0
        shot_errors = 0
        since_last_commit = 0

        for shot_row in shot_data:
            try:
                with db.begin_nested():
                    pid = shot_row.get("PLAYER_ID")
                    if not pid:
                        continue
                    player = db.query(Player).filter(Player.nba_id == pid).first()
                    if not player:
                        continue

                    zone_name = (
                        shot_row.get("ZONE_NAME")
                        or shot_row.get("SHOT_ZONE_BASIC", "Unknown")
                    )
                    fgm = safe_decimal(shot_row.get("FGM"))
                    fga = safe_decimal(shot_row.get("FGA"))
                    fg_pct = safe_decimal(shot_row.get("FG_PCT"))
                    total_fga = safe_decimal(shot_row.get("TOTAL_FGA"))
                    freq = None
                    if total_fga and total_fga > 0 and fga is not None:
                        freq = fga / total_fga
                    league_avg = league_avg_lookup.get(zone_name)

                    shot_values = {
                        "player_id": player.id,
                        "season": season,
                        "zone": zone_name,
                        "fgm": fgm,
                        "fga": fga,
                        "fg_pct": fg_pct,
                        "freq": freq,
                        "league_avg": league_avg,
                    }
                    shot_update = _update_set(shot_values, "player_id", "season", "zone")
                    db.execute(
                        pg_insert(PlayerShotZonesModel)
                        .values(**shot_values)
                        .on_conflict_do_update(
                            index_elements=["player_id", "season", "zone"],
                            set_=shot_update,
                        )
                    )

                shot_processed += 1
                since_last_commit += 1
                if since_last_commit >= BATCH_COMMIT_SIZE:
                    db.commit()
                    since_last_commit = 0

            except _RETRY_EXCEPTIONS:
                db.rollback()
                raise
            except Exception as e:
                logger.error("Error processing shot zone row: %s", e, exc_info=True)
                shot_errors += 1

        db.commit()

        logger.info(
            "Advanced data refresh completed: %d/%d players, %d/%d shot zones, "
            "%d player errors, %d shot-zone errors",
            processed,
            total,
            shot_processed,
            shot_total,
            errors,
            shot_errors,
        )
        return _finalize_task_status(
            task_name="refresh_advanced_data",
            processed=processed,
            errors=errors,
            total=total,
            season=season,
            extra={
                "shot_zones_processed": shot_processed,
                "shot_zones_errors": shot_errors,
                "shot_zones_total": shot_total,
            },
        )

    except RuntimeError:
        db.rollback()
        raise
    except Exception as e:
        logger.exception("Advanced data refresh failed: %s", e)
        db.rollback()
        raise

    finally:
        db.close()


@celery_app.task(
    bind=True,
    autoretry_for=_RETRY_EXCEPTIONS,
    retry_backoff=True,
    retry_backoff_max=600,
    retry_kwargs={"max_retries": 3},
    acks_late=True,
)
def refresh_phase2_data(self, season: str | None = None) -> dict[str, object]:
    """Fetch Phase 2 data: shooting tracking, computed metrics, and career stats.

    Args:
        season: NBA season string. Defaults to current season.

    Returns:
        dict with status, totals, errors, error_rate and season.
    """
    from app.services.nba_data import NBADataService

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
        total = processed + errors

        logger.info(
            "Phase 2 data refresh completed: %d processed, %d errors",
            processed,
            errors,
        )
        return _finalize_task_status(
            task_name="refresh_phase2_data",
            processed=processed,
            errors=errors,
            total=total,
            season=season,
            extra={"part_a": part_a, "part_b": part_b, "part_c": part_c},
        )

    except RuntimeError:
        db.rollback()
        raise
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
