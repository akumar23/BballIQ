#!/usr/bin/env python3
"""Script to fetch all-in-one impact metrics from external sources.

Scrapes EPM, DARKO, LEBRON, and RPM from their respective websites
and stores them in the player_all_in_one_metrics table.

Usage:
    python -m scripts.fetch_all_in_one_data --season 2024-25
    python -m scripts.fetch_all_in_one_data --season 2024-25 --sources epm darko
    python -m scripts.fetch_all_in_one_data --season 2024-25 --verbose
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Player
from app.models.all_in_one_metrics import PlayerAllInOneMetrics
from app.services.all_in_one_scraper import (
    AllInOneMetricsScraper,
    AllInOnePlayerData,
    ScraperResult,
    build_name_lookup,
    match_player,
)
from scripts.shared import setup_logging

logger = logging.getLogger(__name__)

ALL_SOURCES = ["EPM", "DARKO", "LEBRON", "RPM"]

# Maps source name to the model field prefix
SOURCE_FIELD_MAP = {
    "EPM": ("epm", "epm_offense", "epm_defense"),
    "DARKO": ("darko", "darko_offense", "darko_defense"),
    "LEBRON": ("lebron", "lebron_offense", "lebron_defense"),
    "RPM": ("rpm", "rpm_offense", "rpm_defense"),
}


def get_all_players(db: Session) -> list[tuple[int, str]]:
    """Get all active players from DB.

    Returns:
        List of (player.id, player.name) tuples
    """
    players = (
        db.query(Player.id, Player.name)
        .filter(Player.active.is_(True))
        .all()
    )
    return [(p.id, p.name) for p in players]


def store_metrics(
    db: Session,
    season: str,
    source_results: dict[str, ScraperResult],
    name_lookup: dict[str, int],
    verbose: bool = False,
) -> dict[str, int]:
    """Match scraped data to players and store in DB.

    Args:
        db: Database session
        season: NBA season string
        source_results: Dict of source name -> ScraperResult
        name_lookup: Normalized player name -> player DB ID
        verbose: Print detailed progress

    Returns:
        Dict of source name -> number of players matched
    """
    # First pass: collect all matched data per player
    player_data: dict[int, dict] = {}  # player_id -> {field: value}
    match_counts: dict[str, int] = {}

    for source_name, result in source_results.items():
        if not result.success:
            match_counts[source_name] = 0
            continue

        fields = SOURCE_FIELD_MAP.get(source_name)
        if not fields:
            continue

        overall_field, offense_field, defense_field = fields
        matched = 0
        unmatched = []

        for player in result.players:
            player_id = match_player(player.player_name, name_lookup)
            if player_id is None:
                unmatched.append(player.player_name)
                continue

            if player_id not in player_data:
                player_data[player_id] = {"sources": []}

            player_data[player_id][overall_field] = player.overall
            player_data[player_id][offense_field] = player.offense
            player_data[player_id][defense_field] = player.defense
            player_data[player_id]["sources"].append(source_name)
            matched += 1

        match_counts[source_name] = matched

        if verbose and unmatched:
            print(f"  [{source_name}] Unmatched players ({len(unmatched)}):")
            for name in unmatched[:10]:
                print(f"    - {name}")
            if len(unmatched) > 10:
                print(f"    ... and {len(unmatched) - 10} more")

    # Second pass: upsert into database
    stored = 0
    for player_id, data in player_data.items():
        existing = (
            db.query(PlayerAllInOneMetrics)
            .filter(
                PlayerAllInOneMetrics.player_id == player_id,
                PlayerAllInOneMetrics.season == season,
            )
            .first()
        )

        if not existing:
            existing = PlayerAllInOneMetrics(
                player_id=player_id,
                season=season,
            )
            db.add(existing)

        # Set metric values
        for field_name in [
            "epm", "epm_offense", "epm_defense",
            "darko", "darko_offense", "darko_defense",
            "lebron", "lebron_offense", "lebron_defense",
            "rpm", "rpm_offense", "rpm_defense",
        ]:
            if field_name in data:
                setattr(existing, field_name, data[field_name])

        # Track sources
        sources = data.get("sources", [])
        existing_sources = (existing.data_sources or "").split(",")
        all_sources = sorted(
            set(s.strip() for s in existing_sources + sources if s.strip())
        )
        existing.data_sources = ",".join(all_sources)

        stored += 1

    return match_counts


def fetch_and_store_all_in_one_data(
    season: str,
    db: Session,
    sources: list[str] | None = None,
    verbose: bool = False,
) -> bool:
    """Fetch all-in-one metrics and store in DB.

    Args:
        season: NBA season string
        db: Database session
        sources: List of sources to fetch (default: all)
        verbose: Enable verbose logging

    Returns:
        True if at least one source succeeded
    """
    logger.info("Starting all-in-one metrics fetch for season %s", season)
    print(f"\nFetching all-in-one impact metrics for season {season}...")
    print("-" * 50)

    # Step 1: Get player lookup
    print("\nStep 1: Building player name lookup...")
    players = get_all_players(db)
    name_lookup = build_name_lookup(players)
    print(f"  - {len(players)} active players in database")

    if not players:
        print("  [ERROR] No players in database. Run fetch_data.py first.")
        return False

    # Step 2: Scrape external sources
    print("\nStep 2: Scraping external sources...")
    active_sources = sources or ALL_SOURCES

    with AllInOneMetricsScraper() as scraper:
        results = {}

        if "EPM" in active_sources:
            print("\n  Fetching EPM from dunksandthrees.com...")
            results["EPM"] = scraper.fetch_epm()

        if "DARKO" in active_sources:
            print("  Fetching DARKO from darko.app...")
            results["DARKO"] = scraper.fetch_darko()

        if "LEBRON" in active_sources:
            print("  Fetching LEBRON from bball-index.com...")
            results["LEBRON"] = scraper.fetch_lebron()

        if "RPM" in active_sources:
            print("  Fetching RPM from ESPN...")
            results["RPM"] = scraper.fetch_rpm()

    # Print scraping results
    print("\n  Scraping Results:")
    any_success = False
    for source, result in results.items():
        status = "OK" if result.success else "FAILED"
        count = len(result.players) if result.success else 0
        print(f"    {source}: {status} ({count} players)")
        if result.error:
            print(f"      Error: {result.error}")
        if result.success:
            any_success = True

    if not any_success:
        print("\n  [ERROR] All sources failed. No data to store.")
        return False

    # Step 3: Match and store
    print("\nStep 3: Matching players and storing data...")
    match_counts = store_metrics(db, season, results, name_lookup, verbose)

    print("\n  Match Results:")
    for source, count in match_counts.items():
        total = len(results.get(source, ScraperResult(source=source)).players)
        print(f"    {source}: {count}/{total} players matched")

    # Commit
    try:
        db.commit()
        total_stored = sum(match_counts.values())
        print(f"\n  Data committed: {total_stored} total metric entries stored")
    except Exception as e:
        logger.error("Failed to commit: %s", e)
        db.rollback()
        return False

    return True


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Fetch all-in-one impact metrics (EPM, DARKO, LEBRON, RPM)",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m scripts.fetch_all_in_one_data --season 2024-25
    python -m scripts.fetch_all_in_one_data --season 2024-25 --sources epm darko
    python -m scripts.fetch_all_in_one_data --season 2024-25 --verbose
        """,
    )
    parser.add_argument(
        "--season", default="2024-25", help="NBA season (e.g., 2024-25)"
    )
    parser.add_argument(
        "--sources",
        nargs="+",
        choices=[s.lower() for s in ALL_SOURCES],
        help="Specific sources to fetch (default: all)",
    )
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--create-tables", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    # Normalize source names to uppercase
    sources = [s.upper() for s in args.sources] if args.sources else None

    print("\n" + "=" * 60)
    print("StatFloor All-In-One Metrics Fetcher")
    print("=" * 60)
    print(f"\nConfiguration:")
    print(f"  Season: {args.season}")
    print(f"  Sources: {', '.join(sources) if sources else 'All'}")

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
        success = fetch_and_store_all_in_one_data(
            args.season, db, sources=sources, verbose=args.verbose
        )

        if success:
            print(f"\nAll-in-one metrics fetch completed successfully!")
            return 0
        else:
            print(f"\n[ERROR] All-in-one metrics fetch failed")
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
