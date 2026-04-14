#!/usr/bin/env python3
"""Script to fetch player bio data and team records.

Populates:
- Player bio fields (height, weight, country, draft info) from LeagueDashPlayerBioStats
- Team win/loss records from LeagueDashTeamStats

Usage:
    python -m scripts.fetch_bio_data --season 2024-25
    python -m scripts.fetch_bio_data --season 2024-25 --verbose
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Player
from app.services.nba_data import NBADataService
from app.services.rate_limiter import (
    CircuitBreakerError,
    RateLimitError,
    nba_api_circuit_breaker,
)
from app.services.redis_cache import redis_cache

logger = logging.getLogger(__name__)


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def fetch_and_store_bio_data(
    season: str,
    db: Session,
    verbose: bool = False,
    bypass_cache: bool = False,
) -> bool:
    """Fetch player bio data and team records, store in database."""
    logger.info("Starting bio data fetch for season %s", season)
    print(f"\nFetching bio data for season {season}...")
    print("-" * 50)

    service = NBADataService(bypass_cache=bypass_cache)

    # --- Step 1: Player bio data ---
    print("\nStep 1: Fetching player bio stats...")
    try:
        bio_data = service.get_player_bio_stats(season)
        print(f"  - Got bio data for {len(bio_data)} players")
    except (CircuitBreakerError, RateLimitError) as e:
        print(f"  [ERROR] Failed to fetch bio data: {e}")
        return False

    bio_by_nba_id = {p["PLAYER_ID"]: p for p in bio_data}

    # Update Player records
    print("\nStep 2: Updating player bio fields...")
    players = db.query(Player).all()
    updated = 0
    for player in players:
        bio = bio_by_nba_id.get(player.nba_id)
        if not bio:
            continue

        player.height = bio.get("PLAYER_HEIGHT")
        player.weight = int(bio["PLAYER_WEIGHT"]) if bio.get("PLAYER_WEIGHT") and bio["PLAYER_WEIGHT"].isdigit() else None
        player.country = bio.get("COUNTRY")

        draft_year = bio.get("DRAFT_YEAR")
        if draft_year and draft_year != "Undrafted":
            player.draft_year = int(draft_year)
            draft_round = bio.get("DRAFT_ROUND")
            player.draft_round = int(draft_round) if draft_round and draft_round != "Undrafted" else None
            draft_number = bio.get("DRAFT_NUMBER")
            player.draft_number = int(draft_number) if draft_number and draft_number != "Undrafted" else None
        else:
            player.draft_year = None
            player.draft_round = None
            player.draft_number = None

        # Store birth_date from age calculation (approximate: season start year - age)
        age = bio.get("AGE")
        if age is not None:
            # Store the age directly as a string for simplicity
            player.birth_date = str(age)

        updated += 1

    # --- Step 3: Team records ---
    print("\nStep 3: Fetching team records...")
    try:
        team_stats = service.get_team_stats(season, measure_type="Base")
        print(f"  - Got records for {len(team_stats)} teams")
    except (CircuitBreakerError, RateLimitError) as e:
        print(f"  [WARNING] Failed to fetch team stats: {e}")
        team_stats = []

    # Build team wins lookup and cache it for the card API
    team_wins = {}
    for team in team_stats:
        abbr = team.get("TEAM_ABBREVIATION")
        wins = team.get("W")
        losses = team.get("L")
        if abbr and wins is not None:
            team_wins[abbr] = {"wins": wins, "losses": losses}

    if team_wins:
        redis_cache.set(f"team_records:{season}", team_wins, ttl=86400)
        print(f"  - Cached team records for {len(team_wins)} teams")

    # Commit
    try:
        db.commit()
        print(f"\nData committed: {updated} player bios updated")
        logger.info("Committed %d player bios", updated)
    except Exception as e:
        logger.error("Failed to commit: %s", e)
        db.rollback()
        return False

    return True


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch player bio data and team records",
    )
    parser.add_argument("--season", default="2024-25", help="NBA season (e.g., 2024-25)")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    print("\n" + "=" * 60)
    print("NBA Player Bio & Team Records Fetcher")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Season: {args.season}")

    db = SessionLocal()
    try:
        success = fetch_and_store_bio_data(
            args.season, db, verbose=args.verbose, bypass_cache=args.no_cache
        )

        state = nba_api_circuit_breaker.state
        print(f"\nCircuit Breaker Status: {state.value}")

        if success:
            print("\n" + "=" * 60)
            print("Bio data fetch completed successfully!")
            print("=" * 60 + "\n")
            return 0
        else:
            print("\n[ERROR] Bio data fetch failed!")
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
