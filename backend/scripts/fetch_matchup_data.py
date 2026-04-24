#!/usr/bin/env python3
"""Script to fetch player-vs-player matchup data from LeagueSeasonMatchups.

Fetches defensive matchup stats for players in the database and stores
the top matchups per player. Each API call returns all matchups for one
defender, so this script makes one call per player.

Usage:
    python -m scripts.fetch_matchup_data --season 2024-25
    python -m scripts.fetch_matchup_data --season 2024-25 --top-n 10
    python -m scripts.fetch_matchup_data --season 2024-25 --min-minutes 500 --verbose
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Player
from app.models.player_matchups import PlayerMatchups
from app.models.season_stats import SeasonStats
from app.services.nba_data import NBADataService
from app.services.rate_limiter import (
    CircuitBreakerError,
    RateLimitError,
    nba_api_circuit_breaker,
)
from app.services.redis_cache import redis_cache
from scripts.shared import safe_decimal, safe_int, setup_logging

logger = logging.getLogger(__name__)


def get_qualifying_players(
    db: Session, season: str, min_minutes: float = 200
) -> list[tuple[int, int, str]]:
    """Get players who qualify for matchup tracking.

    Returns players with enough minutes to have meaningful matchup data.

    Args:
        db: Database session
        season: NBA season string
        min_minutes: Minimum total minutes to qualify

    Returns:
        List of (player.id, player.nba_id, player.name) tuples
    """
    players = (
        db.query(Player.id, Player.nba_id, Player.name)
        .join(SeasonStats, SeasonStats.player_id == Player.id)
        .filter(
            SeasonStats.season == season,
            SeasonStats.total_minutes >= min_minutes,
            Player.active.is_(True),
        )
        .all()
    )
    return [(p.id, p.nba_id, p.name) for p in players]


def fetch_and_store_matchup_data(
    season: str,
    db: Session,
    top_n: int = 10,
    min_minutes: float = 200,
    verbose: bool = False,
    bypass_cache: bool = False,
) -> bool:
    """Fetch matchup data for qualifying players and store top matchups.

    Args:
        season: NBA season string (e.g., "2024-25")
        db: Database session
        top_n: Number of top matchups to store per player
        min_minutes: Minimum season minutes to qualify
        verbose: Enable verbose logging
        bypass_cache: Skip Redis cache

    Returns:
        True if successful, False otherwise
    """
    logger.info("Starting matchup data fetch for season %s", season)
    print(f"\nFetching matchup data for season {season}...")
    if bypass_cache:
        print("  [INFO] Cache bypass enabled")
    print("-" * 50)

    service = NBADataService(bypass_cache=bypass_cache)

    # Step 1: Get qualifying players
    print("\nStep 1: Finding qualifying players...")
    players = get_qualifying_players(db, season, min_minutes)
    print(f"  - Found {len(players)} players with >= {min_minutes} minutes")

    if not players:
        print("  [WARNING] No qualifying players found. Run fetch_data.py first.")
        return False

    # Step 2: Fetch matchups for each player
    print(f"\nStep 2: Fetching matchup data ({len(players)} players)...")
    print(f"  NOTE: This makes 1 API call per player with rate limiting.")
    print(f"  Expected runtime: ~{len(players) * 0.8:.0f} seconds\n")

    processed = 0
    errors = 0
    total_matchups = 0

    for idx, (player_db_id, player_nba_id, player_name) in enumerate(players):
        try:
            if verbose or (idx + 1) % 25 == 0:
                print(
                    f"  [{idx + 1}/{len(players)}] Fetching matchups for {player_name}..."
                )

            matchups = service.get_matchup_stats(
                season=season, def_player_id=player_nba_id
            )

            # Sort by partial possessions and take top N
            matchups.sort(
                key=lambda m: m.get("PARTIAL_POSS", 0) or 0, reverse=True
            )
            top_matchups = matchups[:top_n]

            # Delete existing matchups for this player/season
            db.query(PlayerMatchups).filter(
                PlayerMatchups.player_id == player_db_id,
                PlayerMatchups.season == season,
            ).delete()

            # Store top matchups
            for matchup in top_matchups:
                record = PlayerMatchups(
                    player_id=player_db_id,
                    season=season,
                    off_player_nba_id=matchup.get("OFF_PLAYER_ID", 0),
                    off_player_name=matchup.get("OFF_PLAYER_NAME", ""),
                    games_played=safe_int(matchup.get("GP")),
                    matchup_min=safe_decimal(matchup.get("MATCHUP_MIN")),
                    partial_poss=safe_decimal(matchup.get("PARTIAL_POSS")),
                    player_pts=safe_decimal(matchup.get("PLAYER_PTS")),
                    team_pts=safe_decimal(matchup.get("TEAM_PTS")),
                    matchup_fgm=safe_decimal(matchup.get("MATCHUP_FGM")),
                    matchup_fga=safe_decimal(matchup.get("MATCHUP_FGA")),
                    matchup_fg_pct=safe_decimal(matchup.get("MATCHUP_FG_PCT")),
                    matchup_fg3m=safe_decimal(matchup.get("MATCHUP_FG3M")),
                    matchup_fg3a=safe_decimal(matchup.get("MATCHUP_FG3A")),
                    matchup_fg3_pct=safe_decimal(matchup.get("MATCHUP_FG3_PCT")),
                    matchup_ftm=safe_decimal(matchup.get("MATCHUP_FTM")),
                    matchup_fta=safe_decimal(matchup.get("MATCHUP_FTA")),
                    matchup_ast=safe_decimal(matchup.get("MATCHUP_AST")),
                    matchup_tov=safe_decimal(matchup.get("MATCHUP_TOV")),
                    matchup_blk=safe_decimal(matchup.get("MATCHUP_BLK")),
                    sfl=safe_decimal(matchup.get("SFL")),
                    help_blk=safe_decimal(matchup.get("HELP_BLK")),
                    help_fgm=safe_decimal(matchup.get("HELP_FGM")),
                    help_fga=safe_decimal(matchup.get("HELP_FGA")),
                    help_fg_pct=safe_decimal(matchup.get("HELP_FG_PERC")),
                )
                db.add(record)

            total_matchups += len(top_matchups)
            processed += 1

            # Periodic commit to avoid large transaction
            if processed % 50 == 0:
                db.commit()
                if verbose:
                    print(f"    Committed batch ({processed} players so far)")

        except (CircuitBreakerError, RateLimitError) as e:
            print(f"  [ERROR] Rate limited at player {player_name}: {e}")
            logger.error("Rate limited at player %s: %s", player_name, e)
            # Commit what we have so far
            db.commit()
            print(f"  Committed {processed} players before rate limit hit.")
            return False

        except Exception as e:
            logger.error("Error fetching matchups for %s: %s", player_name, e)
            errors += 1

    # Final commit
    try:
        db.commit()
        print(f"\nData committed: {processed} players, {total_matchups} matchup records")
        logger.info(
            "Committed %d players, %d matchup records", processed, total_matchups
        )
    except Exception as e:
        logger.error("Failed to commit: %s", e)
        db.rollback()
        return False

    if errors > 0:
        print(f"  [WARNING] {errors} players had errors")

    return True


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch player-vs-player matchup data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m scripts.fetch_matchup_data --season 2024-25
    python -m scripts.fetch_matchup_data --season 2024-25 --top-n 10
    python -m scripts.fetch_matchup_data --season 2024-25 --min-minutes 500
    python -m scripts.fetch_matchup_data --season 2024-25 --no-cache --verbose
        """,
    )
    parser.add_argument(
        "--season", default="2025-26", help="NBA season (e.g., 2025-26)"
    )
    parser.add_argument(
        "--top-n",
        type=int,
        default=10,
        help="Number of top matchups to store per player (default: 10)",
    )
    parser.add_argument(
        "--min-minutes",
        type=float,
        default=200,
        help="Minimum season minutes to qualify (default: 200)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    parser.add_argument("--create-tables", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    print("\n" + "=" * 60)
    print("StatFloor Matchup Data Fetcher")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Season: {args.season}")
    print(f"  Top matchups per player: {args.top_n}")
    print(f"  Min minutes: {args.min_minutes}")
    print(f"  Cache bypass: {args.no_cache}")

    if args.create_tables:
        import subprocess

        print("\nRunning database migrations...")
        subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=Path(__file__).parent.parent,
            check=True,
        )

    db = SessionLocal()
    try:
        success = fetch_and_store_matchup_data(
            args.season,
            db,
            top_n=args.top_n,
            min_minutes=args.min_minutes,
            verbose=args.verbose,
            bypass_cache=args.no_cache,
        )

        state = nba_api_circuit_breaker.state
        print(f"\nCircuit Breaker Status: {state.value}")

        stats = redis_cache.get_stats()
        print(f"Redis Cache: connected={stats.get('connected', False)}")

        if success:
            print(f"\nMatchup data fetch completed successfully!")
            return 0
        else:
            print(f"\n[ERROR] Matchup data fetch failed")
            return 1

    except KeyboardInterrupt:
        print("\n\n[INFO] Interrupted by user")
        return 130
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        print(f"\n[ERROR] Unexpected error: {e}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
