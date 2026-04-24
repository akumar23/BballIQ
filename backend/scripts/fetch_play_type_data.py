#!/usr/bin/env python3
"""Script to fetch play type statistics for all players.

This script fetches offensive play type data from NBA Synergy endpoints:
- Isolation
- Pick and Roll Ball Handler
- Pick and Roll Roll Man
- Post-up
- Spot-up
- Transition
- Cut
- Off-screen
- Handoff

Usage:
    python -m scripts.fetch_play_type_data --season 2024-25
    python -m scripts.fetch_play_type_data --season 2024-25 --create-tables
    python -m scripts.fetch_play_type_data --season 2024-25 --verbose
"""

import argparse
import logging
import sys
from decimal import Decimal
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.db.session import SessionLocal, engine
from app.models import Player, SeasonPlayTypeStats
from app.services.nba_data import NBADataService, PLAY_TYPE_MAPPING
from app.services.rate_limiter import (
    CircuitBreakerError,
    RateLimitError,
    nba_api_circuit_breaker,
)
from app.services.redis_cache import redis_cache
from scripts.shared import create_tables, setup_logging

# Configure logging
logger = logging.getLogger(__name__)

# Minimum possessions threshold for PPP percentile calculation
MIN_POSS_THRESHOLD = 50


def progress_callback(play_type_idx: int, total: int, play_type_name: str) -> None:
    """Print progress for play type data fetching."""
    pass  # Progress is printed in fetch_all_play_type_data


def calculate_metrics(
    poss: int | None,
    pts: int | None,
    fgm: int | None,
    fga: int | None,
    total_poss: int | None,
) -> tuple[Decimal | None, Decimal | None, Decimal | None]:
    """Calculate PPP, FG%, and frequency for a play type.

    Args:
        poss: Number of possessions
        pts: Points scored
        fgm: Field goals made
        fga: Field goals attempted
        total_poss: Total possessions across all play types

    Returns:
        Tuple of (ppp, fg_pct, freq)
    """
    ppp = None
    fg_pct = None
    freq = None

    if poss and poss > 0 and pts is not None:
        ppp = Decimal(str(pts)) / Decimal(str(poss))

    if fga and fga > 0 and fgm is not None:
        fg_pct = Decimal(str(fgm)) / Decimal(str(fga))

    if total_poss and total_poss > 0 and poss:
        freq = Decimal(str(poss)) / Decimal(str(total_poss))

    return ppp, fg_pct, freq


def fetch_and_store_play_type_data(
    season: str,
    db: Session,
    verbose: bool = False,
    bypass_cache: bool = False,
) -> bool:
    """Fetch play type data and store in database.

    Args:
        season: NBA season string (e.g., "2024-25")
        db: Database session
        verbose: If True, print detailed progress
        bypass_cache: If True, skip Redis cache and force API fetch

    Returns:
        True if successful, False otherwise
    """
    logger.info("Starting play type data fetch for season %s", season)
    print(f"\nFetching play type data for season {season}...")
    if bypass_cache:
        print("  [INFO] Cache bypass enabled - forcing fresh API calls")
    print("-" * 50)

    service = NBADataService(bypass_cache=bypass_cache)

    # Step 1: Fetch all play type data
    print(f"\nStep 1: Fetching play type data (9 API calls)...")
    print("  This may take 1-2 minutes with rate limiting...")
    try:
        play_type_data = service.fetch_all_play_type_data(
            season, progress_callback=progress_callback
        )
        print(f"\n  - Collected play type data for {len(play_type_data)} players")
        logger.info("Collected play type data for %d players", len(play_type_data))
    except (CircuitBreakerError, RateLimitError) as e:
        print(f"  [ERROR] Failed to fetch play type data: {e}")
        logger.error("Failed to fetch play type data: %s", e)
        return False

    # Step 2: Store in database
    print("\nStep 2: Storing data in database...")
    processed = 0
    errors = 0
    new_records = 0

    for player_id, data in play_type_data.items():
        try:
            # Get or skip player (must exist from main fetch)
            player = db.query(Player).filter(Player.nba_id == player_id).first()
            if not player:
                logger.debug("Player %d not found, skipping", player_id)
                continue

            # Upsert season play type stats
            stats = (
                db.query(SeasonPlayTypeStats)
                .filter(
                    SeasonPlayTypeStats.player_id == player.id,
                    SeasonPlayTypeStats.season == season,
                )
                .first()
            )

            if not stats:
                stats = SeasonPlayTypeStats(
                    player_id=player.id,
                    season=season,
                )
                db.add(stats)
                new_records += 1

            # Update total possessions
            stats.total_poss = data.total_poss

            # Process each play type
            for field_name in PLAY_TYPE_MAPPING.keys():
                metrics = getattr(data, field_name)
                if metrics is None:
                    continue

                # Set raw stats
                setattr(stats, f"{field_name}_poss", metrics.possessions)
                setattr(stats, f"{field_name}_pts", metrics.points)
                setattr(stats, f"{field_name}_fgm", metrics.fgm)
                setattr(stats, f"{field_name}_fga", metrics.fga)

                # Calculate derived metrics
                ppp, fg_pct, freq = calculate_metrics(
                    metrics.possessions,
                    metrics.points,
                    metrics.fgm,
                    metrics.fga,
                    data.total_poss,
                )
                setattr(stats, f"{field_name}_ppp", ppp)
                setattr(stats, f"{field_name}_fg_pct", fg_pct)
                setattr(stats, f"{field_name}_freq", freq)

                # Handle spot-up 3-point stats
                if field_name == "spot_up" and metrics.fg3m is not None:
                    setattr(stats, "spot_up_fg3m", metrics.fg3m)
                    setattr(stats, "spot_up_fg3a", metrics.fg3a)
                    if metrics.fg3a and metrics.fg3a > 0:
                        fg3_pct = Decimal(str(metrics.fg3m)) / Decimal(str(metrics.fg3a))
                        setattr(stats, "spot_up_fg3_pct", fg3_pct)

            processed += 1

            if verbose and processed % 50 == 0:
                print(f"  Processed {processed} players...")

        except Exception as e:
            logger.error("Error processing player %d: %s", player_id, e)
            errors += 1

    # Commit all changes
    try:
        db.commit()
        print(f"\nData committed to database:")
        print(f"  - {processed} players processed")
        print(f"  - {new_records} new records created")
        logger.info("Committed %d players to database", processed)
    except Exception as e:
        logger.error("Failed to commit data: %s", e)
        db.rollback()
        return False

    if errors > 0:
        print(f"  [WARNING] {errors} players had processing errors")
        logger.warning("%d players had processing errors", errors)

    # Step 3: Calculate percentiles
    print("\nStep 3: Calculating PPP percentiles...")
    calculate_ppp_percentiles(season, db)

    return True


def calculate_ppp_percentiles(season: str, db: Session) -> None:
    """Calculate PPP percentiles for each play type.

    Only considers players with minimum possessions threshold.

    Args:
        season: NBA season string
        db: Database session
    """
    stats_list = (
        db.query(SeasonPlayTypeStats)
        .filter(SeasonPlayTypeStats.season == season)
        .all()
    )

    if not stats_list:
        print("  [WARNING] No play type data found for percentile calculation")
        return

    play_types = [
        "isolation",
        "pnr_ball_handler",
        "pnr_roll_man",
        "post_up",
        "spot_up",
        "transition",
        "cut",
        "off_screen",
        "handoff",
    ]

    for play_type in play_types:
        poss_attr = f"{play_type}_poss"
        ppp_attr = f"{play_type}_ppp"
        percentile_attr = f"{play_type}_ppp_percentile"

        # Filter players with minimum possessions for this play type
        qualified = [
            s for s in stats_list
            if (getattr(s, poss_attr) or 0) >= MIN_POSS_THRESHOLD
            and getattr(s, ppp_attr) is not None
        ]

        if not qualified:
            continue

        # Sort by PPP and assign percentiles
        sorted_players = sorted(qualified, key=lambda x: getattr(x, ppp_attr) or 0)
        for i, stats in enumerate(sorted_players):
            percentile = int((i / len(sorted_players)) * 100)
            setattr(stats, percentile_attr, percentile)

        logger.info(
            "Calculated %s percentiles for %d players (min %d poss)",
            play_type,
            len(qualified),
            MIN_POSS_THRESHOLD,
        )

    db.commit()
    print(f"  Percentiles calculated for {len(stats_list)} players")
    logger.info("Percentiles calculated for %d players", len(stats_list))


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
        description="Fetch play type statistics for all players",
        formatter_class=argparse.RawDescriptionHelpFormatter,
    )
    parser.add_argument(
        "--season",
        default="2025-26",
        help="NBA season (e.g., 2025-26)",
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
    print("NBA Play Type Data Fetcher")
    print("=" * 60)

    print(f"\nConfiguration:")
    print(f"  Season: {args.season}")
    print(f"  Cache bypass: {args.no_cache}")
    print(f"\n  NOTE: This script makes 9 API calls (one per play type)")
    print(f"        Expected runtime: 1-2 minutes with rate limiting")

    if args.create_tables:
        create_tables()

    db = SessionLocal()
    try:
        success = fetch_and_store_play_type_data(
            args.season, db, verbose=args.verbose, bypass_cache=args.no_cache
        )
        print_circuit_breaker_status()
        print_cache_status()

        if success:
            print("\n" + "=" * 60)
            print("Play type data fetch completed successfully!")
            print("=" * 60 + "\n")
            return 0
        else:
            print("\n" + "=" * 60)
            print("[ERROR] Play type data fetch failed!")
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
