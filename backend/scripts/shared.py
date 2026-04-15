"""Shared utilities for data fetch scripts.

Contains common helpers that are duplicated across multiple fetch scripts:
- Logging setup
- Database migration runner
- Season string generation
- Type conversion helpers (Decimal, int)
- NBA ID lookup builder
"""

import logging
import subprocess
import sys
from decimal import Decimal, InvalidOperation
from pathlib import Path

from sqlalchemy.orm import Session

from app.models import Player

# Root of the backend directory
ROOT = Path(__file__).parent.parent


def setup_logging(verbose: bool = False) -> None:
    """Configure logging for a fetch script.

    Args:
        verbose: If True, set DEBUG level; otherwise INFO
    """
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )
    logging.getLogger("app.services.rate_limiter").setLevel(level)
    logging.getLogger("app.services.nba_data").setLevel(level)


def create_tables() -> None:
    """Run Alembic migrations to create/update database tables."""
    logger = logging.getLogger(__name__)
    print("Running database migrations...")
    logger.info("Running database migrations...")
    try:
        result = subprocess.run(
            ["alembic", "upgrade", "head"],
            cwd=ROOT,
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


def generate_seasons(from_season: str, to_season: str) -> list[str]:
    """Generate a list of NBA season strings between two seasons (inclusive).

    Args:
        from_season: Start season in "YYYY-YY" format (e.g., "2013-14")
        to_season: End season in "YYYY-YY" format (e.g., "2024-25")

    Returns:
        Ordered list of season strings from oldest to newest

    Raises:
        ValueError: If from_season is after to_season
    """
    start = int(from_season.split("-")[0])
    end = int(to_season.split("-")[0])

    if start > end:
        raise ValueError(f"from_season {from_season} must be before to_season {to_season}")

    seasons = []
    for year in range(start, end + 1):
        short = str(year + 1)[-2:]
        seasons.append(f"{year}-{short}")
    return seasons


def safe_decimal(value, default=None) -> Decimal | None:
    """Safely convert a value to Decimal.

    Handles None, empty strings, and invalid values gracefully.

    Args:
        value: The value to convert
        default: Value to return if conversion fails

    Returns:
        Decimal value or default
    """
    if value is None or value == "":
        return default
    try:
        return Decimal(str(value))
    except (InvalidOperation, ValueError, TypeError):
        return default


def safe_int(value, default=None) -> int | None:
    """Safely convert a value to int.

    Handles None, empty strings, and invalid values gracefully.
    Converts through float first to handle string representations like "3.0".

    Args:
        value: The value to convert
        default: Value to return if conversion fails

    Returns:
        int value or default
    """
    if value is None or value == "":
        return default
    try:
        return int(float(value))
    except (ValueError, TypeError):
        return default


def build_nba_id_lookup(db: Session) -> dict[int, int]:
    """Build a mapping from NBA player ID to internal database player ID.

    Args:
        db: Database session

    Returns:
        Dict mapping nba_id -> player.id
    """
    return {
        p.nba_id: p.id
        for p in db.query(Player.nba_id, Player.id).all()
    }
