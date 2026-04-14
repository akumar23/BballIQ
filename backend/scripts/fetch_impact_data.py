#!/usr/bin/env python3
"""Script to fetch lineup and on/off data for contextualized impact calculations.

This script fetches:
- 5-man lineup data (1 API call)
- On/off stats for all 30 teams (30 API calls)

And calculates contextualized impact ratings for all players.

Usage:
    python -m scripts.fetch_impact_data --season 2024-25
    python -m scripts.fetch_impact_data --season 2024-25 --create-tables
    python -m scripts.fetch_impact_data --season 2024-25 --verbose
"""

import argparse
import logging
import sys
import time
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.core.config import settings
from app.db.session import SessionLocal, engine
from app.models import ContextualizedImpact, LineupStats, Player, PlayerOnOffStats
from app.services.impact_calculator import ImpactCalculator
from app.services.nba_data import NBADataService
from app.services.rate_limiter import (
    CircuitBreakerError,
    RateLimitError,
    nba_api_circuit_breaker,
)
from app.services.redis_cache import redis_cache


# Configure logging
logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for the script."""
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
        ],
    )
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


def progress_callback(team_idx: int, total_teams: int, team_name: str) -> None:
    """Print progress for on/off data fetching."""
    print(f"  - Fetching on/off stats for {team_name} ({team_idx}/{total_teams})...")


def fetch_and_store_impact_data(
    season: str,
    db: Session,
    verbose: bool = False,
    bypass_cache: bool = False,
) -> bool:
    """Fetch lineup and on/off data, calculate and store impact ratings.

    Args:
        season: NBA season string (e.g., "2024-25")
        db: Database session
        verbose: If True, print detailed progress
        bypass_cache: If True, skip Redis cache and force API fetch

    Returns:
        True if successful, False otherwise
    """
    logger.info("Starting impact data fetch for season %s", season)
    print(f"\nFetching impact data for season {season}...")
    if bypass_cache:
        print("  [INFO] Cache bypass enabled - forcing fresh API calls")
    print("-" * 50)

    service = NBADataService(bypass_cache=bypass_cache)

    # Step 1: Fetch lineup data
    print("\nStep 1: Fetching 5-man lineup data...")
    try:
        lineup_data = service.fetch_lineup_data(season)
        print(f"  - Fetched {len(lineup_data)} lineups")
        logger.info("Fetched %d lineups", len(lineup_data))
    except (CircuitBreakerError, RateLimitError) as e:
        print(f"  [ERROR] Failed to fetch lineup data: {e}")
        logger.error("Failed to fetch lineup data: %s", e)
        return False

    # Step 2: Fetch on/off data (30 team calls)
    print("\nStep 2: Fetching on/off data for all teams (30 API calls)...")
    print("  This may take 1-2 minutes with rate limiting...")
    try:
        on_off_data = service.get_all_on_off_stats(
            season, progress_callback=progress_callback
        )
        print(f"  - Collected on/off data for {len(on_off_data)} players")
        logger.info("Collected on/off data for %d players", len(on_off_data))
    except (CircuitBreakerError, RateLimitError) as e:
        print(f"  [ERROR] Failed to fetch on/off data: {e}")
        logger.error("Failed to fetch on/off data: %s", e)
        return False

    # Step 3: Store lineup data
    print("\nStep 3: Storing lineup data...")
    _store_lineup_data(db, lineup_data, season)

    # Step 4: Calculate contextualized impact
    print("\nStep 4: Calculating contextualized impact ratings...")
    calculator = ImpactCalculator(lineup_data, on_off_data)
    impacts = calculator.calculate_all_impacts()
    print(f"  - Calculated impact for {len(impacts)} players")
    logger.info("Calculated impact for %d players", len(impacts))

    # Step 5: Store on/off and impact data
    print("\nStep 5: Storing on/off and impact data...")
    processed = 0
    errors = 0

    for player_id, on_off in on_off_data.items():
        try:
            # Get or skip player (must exist from main fetch)
            player = db.query(Player).filter(Player.nba_id == player_id).first()
            if not player:
                logger.debug("Player %d not found, skipping", player_id)
                continue

            # Upsert on/off stats
            on_off_stats = (
                db.query(PlayerOnOffStats)
                .filter(
                    PlayerOnOffStats.player_id == player.id,
                    PlayerOnOffStats.season == season,
                )
                .first()
            )

            if not on_off_stats:
                on_off_stats = PlayerOnOffStats(
                    player_id=player.id,
                    season=season,
                )
                db.add(on_off_stats)

            # Update on/off stats
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

            # Upsert contextualized impact if calculated
            impact_data = impacts.get(player_id)
            if impact_data:
                impact = (
                    db.query(ContextualizedImpact)
                    .filter(
                        ContextualizedImpact.player_id == player.id,
                        ContextualizedImpact.season == season,
                    )
                    .first()
                )

                if not impact:
                    impact = ContextualizedImpact(
                        player_id=player.id,
                        season=season,
                    )
                    db.add(impact)

                # Update impact data
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

            if verbose and processed % 50 == 0:
                print(f"  Processed {processed} players...")

        except Exception as e:
            logger.error("Error processing player %d: %s", player_id, e)
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
    print("\nStep 6: Calculating impact percentiles...")
    calculate_impact_percentiles(season, db)

    return True


def _store_lineup_data(
    db: Session,
    lineup_data: list,
    season: str,
) -> None:
    """Persist 5-man lineup data to the lineup_stats table.

    Maps NBA player IDs to internal DB IDs and upserts each lineup row.
    """
    # Build nba_id -> internal id lookup
    players = db.query(Player.nba_id, Player.id).all()
    nba_to_db: dict[int, int] = {int(p.nba_id): int(p.id) for p in players}

    # Clear existing lineup data for this season
    db.query(LineupStats).filter(LineupStats.season == season).delete()

    stored = 0
    skipped = 0
    for lineup in lineup_data:
        # Resolve all 5 player IDs to internal DB IDs
        db_ids = [nba_to_db.get(pid) for pid in sorted(lineup.player_ids)]
        if None in db_ids or len(db_ids) != 5:
            skipped += 1
            continue

        row = LineupStats(
            season=season,
            team_id=lineup.team_id,
            team_abbreviation=lineup.team_abbreviation,
            lineup_id=lineup.lineup_id,
            group_name="-".join(lineup.player_names) if lineup.player_names else None,
            player1_id=db_ids[0],
            player2_id=db_ids[1],
            player3_id=db_ids[2],
            player4_id=db_ids[3],
            player5_id=db_ids[4],
            games_played=lineup.games_played,
            minutes=lineup.minutes,
            plus_minus=lineup.plus_minus,
            off_rating=lineup.off_rating,
            def_rating=lineup.def_rating,
            net_rating=lineup.net_rating,
        )
        db.add(row)
        stored += 1

    db.flush()
    print(f"  - Stored {stored} lineups ({skipped} skipped — missing players)")
    logger.info("Stored %d lineups (%d skipped)", stored, skipped)


def calculate_impact_percentiles(season: str, db: Session) -> None:
    """Calculate percentiles for impact ratings.

    Args:
        season: NBA season string
        db: Database session
    """
    impacts = (
        db.query(ContextualizedImpact)
        .filter(ContextualizedImpact.season == season)
        .filter(ContextualizedImpact.contextualized_net_impact.isnot(None))
        .all()
    )

    if not impacts:
        print("  [WARNING] No impact data found for percentile calculation")
        return

    # Sort by net impact
    net_sorted = sorted(impacts, key=lambda x: x.contextualized_net_impact or 0)
    for i, impact in enumerate(net_sorted):
        impact.impact_percentile = int((i / len(net_sorted)) * 100)

    # Sort by offensive impact
    off_sorted = sorted(impacts, key=lambda x: x.contextualized_off_impact or 0)
    for i, impact in enumerate(off_sorted):
        impact.offensive_impact_percentile = int((i / len(off_sorted)) * 100)

    # Sort by defensive impact (lower is better for defense, so reverse logic)
    def_sorted = sorted(impacts, key=lambda x: x.contextualized_def_impact or 0)
    for i, impact in enumerate(def_sorted):
        # Lower def rating = better defense = higher percentile
        impact.defensive_impact_percentile = int(((len(def_sorted) - i - 1) / len(def_sorted)) * 100)

    db.commit()
    print(f"  Percentiles calculated for {len(impacts)} players")
    logger.info("Percentiles calculated for %d players", len(impacts))


def print_circuit_breaker_status() -> None:
    """Print current circuit breaker status."""
    state = nba_api_circuit_breaker.state
    print(f"\nCircuit Breaker Status: {state.value}")
    logger.info("Circuit breaker status: %s", state.value)


def print_cache_status() -> None:
    """Print current Redis cache status."""
    stats = redis_cache.get_stats()
    print(f"\nRedis Cache Status:")
    print(f"  Connected: {stats.get('connected', False)}")
    print(f"  Enabled: {stats.get('enabled', False)}")
    if stats.get("connected"):
        print(f"  Cache hits: {stats.get('hits', 0)}")
        print(f"  Cache misses: {stats.get('misses', 0)}")


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch lineup and on/off data for impact calculations",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--season",
        default="2024-25",
        help="NBA season (e.g., 2024-25)",
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
    args = parser.parse_args()

    setup_logging(args.verbose)

    print("\n" + "=" * 60)
    print("NBA Contextualized Impact Data Fetcher")
    print("=" * 60)

    print(f"\nConfiguration:")
    print(f"  Season: {args.season}")
    print(f"  Cache bypass: {args.no_cache}")
    print(f"\n  NOTE: This script makes ~31 API calls (lineup + 30 teams)")
    print(f"        Expected runtime: 1-2 minutes with rate limiting")

    if args.create_tables:
        create_tables()

    db = SessionLocal()
    try:
        success = fetch_and_store_impact_data(
            args.season, db, verbose=args.verbose, bypass_cache=args.no_cache
        )
        print_circuit_breaker_status()
        print_cache_status()

        if success:
            print("\n" + "=" * 60)
            print("Impact data fetch completed successfully!")
            print("=" * 60 + "\n")
            return 0
        else:
            print("\n" + "=" * 60)
            print("[ERROR] Impact data fetch failed!")
            print("=" * 60 + "\n")
            return 1

    except KeyboardInterrupt:
        print("\n\n[INFO] Interrupted by user")
        logger.info("Script interrupted by user")
        return 130

    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        print(f"\n[ERROR] Unexpected error: {e}")
        return 1

    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
