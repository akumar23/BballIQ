#!/usr/bin/env python3
"""Script to fetch all NBA tracking data and populate the database.

This script implements robust error handling with:
- Exponential backoff for rate limiting
- Circuit breaker protection
- Progress tracking and resumption
- Comprehensive logging

Usage:
    python -m scripts.fetch_data --season 2024-25
    python -m scripts.fetch_data --season 2024-25 --create-tables
    python -m scripts.fetch_data --season 2024-25 --verbose
    python -m scripts.fetch_data --from-season 2020-21
    python -m scripts.fetch_data --seasons 2022-23 2023-24 2024-25
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from decimal import Decimal

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.models import Per75Stats, Player, SeasonStats
from app.services.metrics import MetricsCalculator
from app.services.nba_data import NBADataService, PlayerTrackingData, nba_data_service
from app.services.per_75_calculator import per_75_calculator
from app.services.rate_limiter import (
    CircuitBreakerError,
    RateLimitError,
    nba_api_circuit_breaker,
)
from app.services.redis_cache import redis_cache


# Configure logging
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the script.

    Args:
        verbose: If True, set DEBUG level; otherwise INFO
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
    # Also configure the rate_limiter logger
    logging.getLogger("app.services.rate_limiter").setLevel(level)
    logging.getLogger("app.services.nba_data").setLevel(level)


def create_tables() -> None:
    """Run Alembic migrations to create/update database tables."""
    import subprocess

    print("Running database migrations...")
    logger.info("Running database migrations...")
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=Path(__file__).parent.parent,
            capture_output=True,
            text=True,
            check=True,
        )
        if result.stdout:
            print(result.stdout)
        print("Done.")
        logger.info("Database migrations completed successfully")
    except subprocess.CalledProcessError as e:
        logger.error("Migration failed: %s", e.stderr)
        print(f"[ERROR] Migration failed: {e.stderr}")
        raise


def fetch_tracking_data_with_recovery(
    service: NBADataService,
    season: str,
    max_recovery_attempts: int = 3,
) -> dict[int, PlayerTrackingData] | None:
    """Fetch tracking data with circuit breaker recovery handling.

    This function handles CircuitBreakerError by waiting for recovery
    and retrying the entire fetch operation.

    Args:
        service: NBADataService instance
        season: NBA season string
        max_recovery_attempts: Maximum times to wait for circuit recovery

    Returns:
        Dictionary of PlayerTrackingData if successful, None if failed
    """
    for recovery_attempt in range(max_recovery_attempts):
        try:
            return service.fetch_all_tracking_data(season)

        except CircuitBreakerError as e:
            logger.warning(
                "Circuit breaker open (recovery attempt %d/%d). "
                "Waiting %.1fs for recovery...",
                recovery_attempt + 1,
                max_recovery_attempts,
                e.recovery_time,
            )
            print(
                f"  [WARNING] Circuit breaker open. "
                f"Waiting {e.recovery_time:.1f}s for recovery..."
            )

            # Wait for recovery plus a small buffer
            time.sleep(e.recovery_time + 5)

            # Reset circuit breaker if we've waited long enough
            if recovery_attempt >= max_recovery_attempts - 1:
                logger.info("Manually resetting circuit breaker for final attempt")
                nba_api_circuit_breaker.reset()

        except RateLimitError as e:
            logger.error(
                "Rate limited after all retries. Suggested wait: %.1fs",
                e.retry_after or 60,
            )
            print(
                f"  [ERROR] Rate limited! Suggested wait: "
                f"{e.retry_after or 60:.1f}s"
            )

            if recovery_attempt < max_recovery_attempts - 1:
                wait_time = e.retry_after or 60
                print(f"  Waiting {wait_time:.1f}s before retry...")
                time.sleep(wait_time)
            else:
                return None

    logger.error("Failed to fetch tracking data after all recovery attempts")
    return None


def fetch_and_store_data(
    season: str,
    db: Session,
    verbose: bool = False,
    bypass_cache: bool = False,
) -> bool:
    """Fetch all tracking data and store in database.

    Args:
        season: NBA season string (e.g., "2024-25")
        db: Database session
        verbose: If True, print detailed progress
        bypass_cache: If True, skip Redis cache and force API fetch

    Returns:
        True if successful, False otherwise
    """
    logger.info("Starting data fetch for season %s", season)
    print(f"\nFetching data for season {season}...")
    if bypass_cache:
        print("  [INFO] Cache bypass enabled - forcing fresh API calls")
        logger.info("Cache bypass enabled")
    print("-" * 50)

    # Create a service instance (uses singleton's circuit breaker)
    service = NBADataService(bypass_cache=bypass_cache)

    # Fetch combined tracking data with recovery handling
    tracking_data = fetch_tracking_data_with_recovery(service, season)

    if not tracking_data:
        print("[ERROR] No tracking data fetched!")
        logger.error("Failed to fetch tracking data for season %s", season)
        return False

    logger.info("Successfully fetched data for %d players", len(tracking_data))

    # Calculate league averages for normalization
    total_touches = sum(p.touches for p in tracking_data.values())
    league_avg_touches = Decimal(total_touches) / Decimal(len(tracking_data))
    print(f"\nLeague average touches: {league_avg_touches:.1f}")
    logger.info("League average touches: %.1f", league_avg_touches)

    # Initialize metrics calculator
    calculator = MetricsCalculator(league_avg_touches)

    # Process each player
    print(f"Processing {len(tracking_data)} players...")
    logger.info("Processing %d players", len(tracking_data))

    processed = 0
    errors = 0

    for player_id, data in tracking_data.items():
        try:
            # Upsert player using ON CONFLICT DO NOTHING to avoid UniqueViolation
            # when re-running for multiple seasons (players already exist from prior runs)
            from sqlalchemy.dialects.postgresql import insert as pg_insert
            stmt = pg_insert(Player.__table__).values(
                nba_id=player_id,
                name=data.player_name,
                team_abbreviation=data.team_abbreviation,
                active=True,
            ).on_conflict_do_nothing(index_elements=["nba_id"])
            db.execute(stmt)
            db.flush()
            player = db.query(Player).filter(Player.nba_id == player_id).first()

            # Calculate rates for metrics
            if data.touches > 0:
                assist_rate = Decimal(data.assists) / Decimal(data.touches)
                turnover_rate = Decimal(data.turnovers) / Decimal(data.touches)
                ft_rate = Decimal(data.fta) / Decimal(data.touches)
            else:
                assist_rate = Decimal(0)
                turnover_rate = Decimal(0)
                ft_rate = Decimal(0)

            # Calculate offensive metric
            offensive_metric = calculator.calculate_offensive_metric(
                points_per_touch=data.points_per_touch,
                assist_rate=assist_rate,
                turnover_rate=turnover_rate,
                ft_rate=ft_rate,
                total_touches=data.touches,
            )

            # Estimate defensive possessions (minutes * ~2 possessions per minute)
            est_def_possessions = int(data.minutes * 2)

            # Calculate per-100 defensive rates
            if est_def_possessions > 0:
                deflections_per_100 = (
                    Decimal(data.deflections * 100) / Decimal(est_def_possessions)
                )
                total_contests = data.contested_shots_2pt + data.contested_shots_3pt
                contests_per_100 = (
                    Decimal(total_contests * 100) / Decimal(est_def_possessions)
                )
                # Steals not in tracking data, estimate from traditional
                steals_per_100 = Decimal(0)  # Would need to add steals to tracking data
                charges_per_100 = (
                    Decimal(data.charges_drawn * 100) / Decimal(est_def_possessions)
                )
                loose_balls_per_100 = (
                    Decimal(data.loose_balls_recovered * 100)
                    / Decimal(est_def_possessions)
                )
            else:
                deflections_per_100 = Decimal(0)
                contests_per_100 = Decimal(0)
                steals_per_100 = Decimal(0)
                charges_per_100 = Decimal(0)
                loose_balls_per_100 = Decimal(0)

            # Calculate defensive metric
            defensive_metric = calculator.calculate_defensive_metric(
                deflections_per_100=deflections_per_100,
                contests_per_100=contests_per_100,
                steals_per_100=steals_per_100,
                charges_per_100=charges_per_100,
                loose_balls_per_100=loose_balls_per_100,
                total_possessions=est_def_possessions,
            )

            # Overall metric (weighted average)
            if offensive_metric > 0 or defensive_metric > 0:
                overall_metric = (
                    offensive_metric * Decimal("0.6")
                    + defensive_metric * Decimal("0.4")
                )
            else:
                overall_metric = Decimal(0)

            # Upsert season stats
            season_stats = (
                db.query(SeasonStats)
                .filter(
                    SeasonStats.player_id == player.id,
                    SeasonStats.season == season,
                )
                .first()
            )

            if not season_stats:
                season_stats = SeasonStats(
                    player_id=player.id,
                    season=season,
                )
                db.add(season_stats)

            # Update game info
            season_stats.games_played = data.games_played
            season_stats.total_minutes = data.minutes

            # Update traditional box score stats
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

            # Update touch tracking stats
            season_stats.total_touches = data.touches
            season_stats.total_front_court_touches = data.front_court_touches
            season_stats.total_time_of_possession = data.time_of_possession
            season_stats.avg_points_per_touch = data.points_per_touch

            # Update hustle/defensive stats
            season_stats.total_deflections = data.deflections
            season_stats.total_contested_shots = (
                data.contested_shots_2pt + data.contested_shots_3pt
            )
            season_stats.total_contested_shots_2pt = data.contested_shots_2pt
            season_stats.total_contested_shots_3pt = data.contested_shots_3pt
            season_stats.total_charges_drawn = data.charges_drawn
            season_stats.total_loose_balls_recovered = data.loose_balls_recovered
            season_stats.total_box_outs = data.box_outs
            season_stats.total_box_outs_off = data.box_outs_off
            season_stats.total_box_outs_def = data.box_outs_def
            season_stats.total_screen_assists = data.screen_assists
            season_stats.games_played = data.games_played
            season_stats.total_fta = data.fta
            season_stats.total_ftm = data.ftm
            season_stats.total_rebounds = data.rebounds
            season_stats.total_screen_assist_pts = data.screen_assist_pts

            # Store estimated possessions
            season_stats.estimated_possessions = est_def_possessions

            # Update calculated metrics
            season_stats.offensive_metric = offensive_metric
            season_stats.defensive_metric = defensive_metric
            season_stats.overall_metric = overall_metric

            # Flush to get the season_stats ID for per_75_stats relationship
            db.flush()

            # Calculate and store per-75 stats
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

            # Upsert per_75_stats
            per_75_stats = (
                db.query(Per75Stats)
                .filter(Per75Stats.season_stats_id == season_stats.id)
                .first()
            )

            if not per_75_stats:
                per_75_stats = Per75Stats(
                    season_stats_id=season_stats.id,
                    season=season,
                )
                db.add(per_75_stats)

            # Update per 75 stats
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

            # Progress indicator
            if verbose and processed % 50 == 0:
                print(f"  Processed {processed}/{len(tracking_data)} players...")

        except Exception as e:
            logger.error(
                "Error processing player %d (%s): %s",
                player_id,
                data.player_name,
                e,
            )
            errors += 1

    # Commit all changes
    try:
        db.commit()
        print(f"\nData committed to database: {processed} players processed")
        logger.info("Committed %d players to database", processed)
    except Exception as e:
        logger.error("Failed to commit data: %s", e)
        db.rollback()
        return False

    if errors > 0:
        print(f"  [WARNING] {errors} players had processing errors")
        logger.warning("%d players had processing errors", errors)

    # Calculate percentiles
    print("\nCalculating percentiles...")
    logger.info("Calculating percentiles")
    calculate_percentiles(season, db)

    return True


def calculate_percentiles(season: str, db: Session) -> None:
    """Calculate league percentiles for all players.

    Args:
        season: NBA season string
        db: Database session
    """
    stats = (
        db.query(SeasonStats)
        .filter(SeasonStats.season == season)
        .filter(SeasonStats.offensive_metric > 0)
        .all()
    )

    if not stats:
        logger.warning("No stats found for percentile calculation")
        print("  [WARNING] No stats found for percentile calculation")
        return

    # Sort by offensive metric
    off_sorted = sorted(stats, key=lambda x: x.offensive_metric or 0)
    for i, stat in enumerate(off_sorted):
        stat.offensive_percentile = int((i / len(off_sorted)) * 100)

    # Sort by defensive metric
    def_sorted = sorted(stats, key=lambda x: x.defensive_metric or 0)
    for i, stat in enumerate(def_sorted):
        stat.defensive_percentile = int((i / len(def_sorted)) * 100)

    db.commit()
    print(f"  Percentiles calculated for {len(stats)} players")
    logger.info("Percentiles calculated for %d players", len(stats))


def generate_season_range(from_season: str, to_season: str) -> list[str]:
    """Generate a list of NBA season strings between two seasons (inclusive).

    Args:
        from_season: Start season in "YYYY-YY" format (e.g., "2020-21")
        to_season: End season in "YYYY-YY" format (e.g., "2024-25")

    Returns:
        Ordered list of season strings from oldest to newest
    """
    def parse_start_year(season: str) -> int:
        return int(season.split("-")[0])

    start = parse_start_year(from_season)
    end = parse_start_year(to_season)

    if start > end:
        raise ValueError(f"from-season {from_season} must be before to-season {to_season}")

    seasons = []
    for year in range(start, end + 1):
        short_year = str(year + 1)[-2:]
        seasons.append(f"{year}-{short_year}")
    return seasons


def print_circuit_breaker_status() -> None:
    """Print current circuit breaker status."""
    state = nba_api_circuit_breaker.state
    print(f"\nCircuit Breaker Status: {state.value}")
    logger.info("Circuit breaker status: %s", state.value)

    if nba_api_circuit_breaker._failure_count > 0:
        print(f"  Failure count: {nba_api_circuit_breaker._failure_count}")


def print_cache_status() -> None:
    """Print current Redis cache status."""
    stats = redis_cache.get_stats()
    print(f"\nRedis Cache Status:")
    print(f"  Connected: {stats.get('connected', False)}")
    print(f"  Enabled: {stats.get('enabled', False)}")
    if stats.get("connected"):
        print(f"  Cache hits: {stats.get('hits', 0)}")
        print(f"  Cache misses: {stats.get('misses', 0)}")
        print(f"  Total keys: {stats.get('keys', 0)}")
    elif stats.get("error"):
        print(f"  Error: {stats.get('error')}")


def main() -> int:
    """Main entry point.

    Returns:
        Exit code (0 for success, 1 for failure)
    """
    parser = argparse.ArgumentParser(
        description="Fetch NBA tracking data and populate database",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m scripts.fetch_data --season 2024-25
    python -m scripts.fetch_data --season 2024-25 --create-tables
    python -m scripts.fetch_data --season 2024-25 --verbose
    python -m scripts.fetch_data --season 2024-25 --no-cache
    python -m scripts.fetch_data --from-season 2020-21
    python -m scripts.fetch_data --from-season 2020-21 --season 2024-25
    python -m scripts.fetch_data --seasons 2022-23 2023-24 2024-25
    python -m scripts.fetch_data --invalidate-cache 2024-25

Environment variables for rate limiting:
    NBA_API_BASE_DELAY: Base delay between requests (default: 0.6s)
    NBA_API_MAX_RETRIES: Maximum retry attempts (default: 5)
    NBA_API_BACKOFF_MAX: Maximum backoff delay (default: 60s)
    CIRCUIT_BREAKER_FAILURE_THRESHOLD: Failures before circuit opens (default: 5)
    CIRCUIT_BREAKER_RECOVERY_TIMEOUT: Recovery wait time (default: 60s)

Environment variables for caching:
    CACHE_ENABLED: Enable/disable Redis caching (default: True)
    CACHE_TTL_DEFAULT: Default cache TTL in seconds (default: 86400)
    CACHE_TTL_PLAYERS: Player data TTL (default: 86400)
    CACHE_TTL_TRACKING_STATS: Tracking stats TTL (default: 86400)
    CACHE_TTL_GAME_POSSESSIONS: Game possession TTL (default: 604800)
        """,
    )
    parser.add_argument(
        "--season",
        default="2024-25",
        help="NBA season to fetch (e.g., 2024-25). Used as the end season when --from-season is set.",
    )
    parser.add_argument(
        "--seasons",
        nargs="+",
        metavar="SEASON",
        help="Fetch an explicit list of seasons (e.g., --seasons 2022-23 2023-24 2024-25). Overrides --season and --from-season.",
    )
    parser.add_argument(
        "--from-season",
        metavar="SEASON",
        help="Fetch all seasons from this season up to --season (e.g., --from-season 2020-21).",
    )
    parser.add_argument(
        "--create-tables",
        action="store_true",
        help="Create database tables before fetching",
    )
    parser.add_argument(
        "--verbose",
        "-v",
        action="store_true",
        help="Enable verbose logging",
    )
    parser.add_argument(
        "--no-cache",
        action="store_true",
        help="Bypass Redis cache and force fresh API calls",
    )
    parser.add_argument(
        "--invalidate-cache",
        metavar="SEASON",
        help="Invalidate cache for a specific season and exit (e.g., 2024-25)",
    )
    args = parser.parse_args()

    # Setup logging
    setup_logging(args.verbose)

    print("\n" + "=" * 60)
    print("StatFloor Data Fetcher")
    print("=" * 60)

    # Handle cache invalidation command
    if args.invalidate_cache:
        print(f"\nInvalidating cache for season {args.invalidate_cache}...")
        deleted = redis_cache.invalidate_season(args.invalidate_cache)
        print(f"  Deleted {deleted} cache keys")
        print_cache_status()
        return 0

    # Determine which seasons to fetch
    if args.seasons:
        seasons_to_fetch = args.seasons
    elif args.from_season:
        try:
            seasons_to_fetch = generate_season_range(args.from_season, args.season)
        except ValueError as e:
            print(f"[ERROR] {e}")
            return 1
    else:
        seasons_to_fetch = [args.season]

    print(f"\nConfiguration:")
    print(f"  Seasons: {', '.join(seasons_to_fetch)}")
    print(f"  Base delay: {settings.nba_api_base_delay}s")
    print(f"  Max retries: {settings.nba_api_max_retries}")
    print(f"  Backoff max: {settings.nba_api_backoff_max}s")
    print(f"  Circuit breaker threshold: {settings.circuit_breaker_failure_threshold}")
    print(f"  Circuit breaker recovery: {settings.circuit_breaker_recovery_timeout}s")
    print(f"  Cache enabled: {settings.cache_enabled}")
    print(f"  Cache bypass: {args.no_cache}")
    print(f"  Cache TTL (default): {settings.cache_ttl_default}s ({settings.cache_ttl_default // 3600}h)")

    if args.create_tables:
        create_tables()

    db = SessionLocal()
    try:
        failed_seasons = []
        for i, season in enumerate(seasons_to_fetch):
            if len(seasons_to_fetch) > 1:
                print(f"\n{'=' * 60}")
                print(f"Season {i + 1}/{len(seasons_to_fetch)}: {season}")
                print("=" * 60)

            success = fetch_and_store_data(
                season, db, verbose=args.verbose, bypass_cache=args.no_cache
            )

            if not success:
                failed_seasons.append(season)
                logger.error("Failed to fetch data for season %s", season)

        print_circuit_breaker_status()
        print_cache_status()

        if not failed_seasons:
            print("\n" + "=" * 60)
            seasons_label = ", ".join(seasons_to_fetch)
            print(f"Data fetch completed successfully! ({seasons_label})")
            print("=" * 60 + "\n")
            return 0
        else:
            print("\n" + "=" * 60)
            print(f"[ERROR] Data fetch failed for: {', '.join(failed_seasons)}")
            print("=" * 60 + "\n")
            return 1

    except KeyboardInterrupt:
        print("\n\n[INFO] Interrupted by user")
        logger.info("Script interrupted by user")
        print_circuit_breaker_status()
        print_cache_status()
        return 130

    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        print(f"\n[ERROR] Unexpected error: {e}")
        print_circuit_breaker_status()
        print_cache_status()
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
