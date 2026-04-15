#!/usr/bin/env python3
"""Script to fetch advanced tracking data for all players.

Populates:
- Speed & Distance tracking
- Passing tracking
- Rebounding tracking (contested/uncontested)
- Closest defender distance shooting
- Defensive play types (Synergy)

Usage:
    python -m scripts.fetch_tracking_advanced --season 2024-25
    python -m scripts.fetch_tracking_advanced --season 2024-25 --verbose
"""

import argparse
import logging
import sys
from decimal import Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Player
from app.models.speed_distance import PlayerSpeedDistance
from app.models.passing_stats import PlayerPassingStats
from app.models.rebounding_tracking import PlayerReboundingTracking
from app.models.defender_distance_shooting import PlayerDefenderDistanceShooting
from app.models.defensive_play_types import PlayerDefensivePlayTypes
from app.services.nba_data import NBADataService, DEFENSIVE_PLAY_TYPE_MAPPING
from app.services.rate_limiter import (
    CircuitBreakerError,
    RateLimitError,
    nba_api_circuit_breaker,
)
from app.services.redis_cache import redis_cache

logger = logging.getLogger(__name__)

# Defender distance ranges from NBA API
DEFENDER_DISTANCE_RANGES = {
    "very_tight": "0-2 Feet - Very Tight",
    "tight": "2-4 Feet - Tight",
    "open": "4-6 Feet - Open",
    "wide_open": "6+ Feet - Wide Open",
}

# Maps internal field names to DEFENSIVE_PLAY_TYPE_MAPPING keys
DEF_PLAY_TYPE_FIELDS = {
    "isolation": "Isolation",
    "pnr_ball_handler": "PRBallHandler",
    "post_up": "Postup",
    "spot_up": "Spotup",
    "transition": "Transition",
}


def setup_logging(verbose: bool = False) -> None:
    level = logging.DEBUG if verbose else logging.INFO
    logging.basicConfig(
        level=level,
        format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
        handlers=[logging.StreamHandler(sys.stdout)],
    )


def _d(val) -> Decimal | None:
    """Convert API value to Decimal or None."""
    if val is None:
        return None
    return Decimal(str(val))


def _build_nba_id_lookup(db: Session) -> dict[int, int]:
    """Build nba_id -> player.id lookup."""
    return {
        p.nba_id: p.id
        for p in db.query(Player.nba_id, Player.id).all()
    }


def fetch_speed_distance(service: NBADataService, season: str, db: Session, lookup: dict) -> int:
    """Fetch and store speed & distance tracking data."""
    print("\n  [1/5] Fetching speed & distance tracking...")
    try:
        data = service.get_speed_distance_stats(season)
    except (CircuitBreakerError, RateLimitError) as e:
        print(f"    [ERROR] {e}")
        return 0

    count = 0
    for row in data:
        pid = lookup.get(row.get("PLAYER_ID"))
        if not pid:
            continue

        rec = (
            db.query(PlayerSpeedDistance)
            .filter(PlayerSpeedDistance.player_id == pid, PlayerSpeedDistance.season == season)
            .first()
        )
        if not rec:
            rec = PlayerSpeedDistance(player_id=pid, season=season)
            db.add(rec)

        rec.dist_feet = _d(row.get("DIST_FEET"))
        rec.dist_miles = _d(row.get("DIST_MILES"))
        rec.dist_miles_off = _d(row.get("DIST_MILES_OFF"))
        rec.dist_miles_def = _d(row.get("DIST_MILES_DEF"))
        rec.avg_speed = _d(row.get("AVG_SPEED"))
        rec.avg_speed_off = _d(row.get("AVG_SPEED_OFF"))
        rec.avg_speed_def = _d(row.get("AVG_SPEED_DEF"))
        count += 1

    print(f"    Stored for {count} players")
    return count


def fetch_passing(service: NBADataService, season: str, db: Session, lookup: dict) -> int:
    """Fetch and store passing tracking data."""
    print("\n  [2/5] Fetching passing tracking...")
    try:
        data = service.get_passing_stats(season)
    except (CircuitBreakerError, RateLimitError) as e:
        print(f"    [ERROR] {e}")
        return 0

    count = 0
    for row in data:
        pid = lookup.get(row.get("PLAYER_ID"))
        if not pid:
            continue

        rec = (
            db.query(PlayerPassingStats)
            .filter(PlayerPassingStats.player_id == pid, PlayerPassingStats.season == season)
            .first()
        )
        if not rec:
            rec = PlayerPassingStats(player_id=pid, season=season)
            db.add(rec)

        rec.passes_made = _d(row.get("PASSES_MADE"))
        rec.passes_received = _d(row.get("PASSES_RECEIVED"))
        rec.ft_ast = _d(row.get("FT_AST"))
        rec.secondary_ast = _d(row.get("SECONDARY_AST"))
        rec.potential_ast = _d(row.get("POTENTIAL_AST"))
        rec.ast_points_created = _d(row.get("AST_POINTS_CREATED"))
        rec.ast_adj = _d(row.get("AST_ADJ"))
        rec.ast_to_pass_pct = _d(row.get("AST_TO_PASS_PCT"))
        rec.ast_to_pass_pct_adj = _d(row.get("AST_TO_PASS_PCT_ADJ"))
        count += 1

    print(f"    Stored for {count} players")
    return count


def fetch_rebounding(service: NBADataService, season: str, db: Session, lookup: dict) -> int:
    """Fetch and store rebounding tracking data."""
    print("\n  [3/5] Fetching rebounding tracking...")
    try:
        data = service.get_rebounding_tracking_stats(season)
    except (CircuitBreakerError, RateLimitError) as e:
        print(f"    [ERROR] {e}")
        return 0

    count = 0
    for row in data:
        pid = lookup.get(row.get("PLAYER_ID"))
        if not pid:
            continue

        rec = (
            db.query(PlayerReboundingTracking)
            .filter(PlayerReboundingTracking.player_id == pid, PlayerReboundingTracking.season == season)
            .first()
        )
        if not rec:
            rec = PlayerReboundingTracking(player_id=pid, season=season)
            db.add(rec)

        for prefix in ("OREB", "DREB", "REB"):
            col_prefix = prefix.lower()
            setattr(rec, col_prefix, _d(row.get(prefix)))
            setattr(rec, f"{col_prefix}_contest", _d(row.get(f"{prefix}_CONTEST")))
            setattr(rec, f"{col_prefix}_uncontest", _d(row.get(f"{prefix}_UNCONTEST")))
            setattr(rec, f"{col_prefix}_contest_pct", _d(row.get(f"{prefix}_CONTEST_PCT")))
            setattr(rec, f"{col_prefix}_chances", _d(row.get(f"{prefix}_CHANCES")))
            setattr(rec, f"{col_prefix}_chance_pct", _d(row.get(f"{prefix}_CHANCE_PCT")))
            setattr(rec, f"{col_prefix}_chance_defer", _d(row.get(f"{prefix}_CHANCE_DEFER")))
            setattr(rec, f"{col_prefix}_chance_pct_adj", _d(row.get(f"{prefix}_CHANCE_PCT_ADJ")))
            setattr(rec, f"avg_{col_prefix}_dist", _d(row.get(f"AVG_{prefix}_DIST")))
        count += 1

    print(f"    Stored for {count} players")
    return count


def fetch_defender_distance(service: NBADataService, season: str, db: Session, lookup: dict) -> int:
    """Fetch and store closest defender distance shooting data."""
    print("\n  [4/5] Fetching defender distance shooting (4 API calls)...")

    # Collect all distance range data keyed by player
    player_data: dict[int, dict] = {}  # nba_id -> {range_prefix: row}

    for prefix, api_range in DEFENDER_DISTANCE_RANGES.items():
        print(f"    Fetching {prefix} ({api_range})...")
        try:
            data = service.get_defender_distance_shooting(season, api_range)
        except (CircuitBreakerError, RateLimitError) as e:
            print(f"      [ERROR] {e}")
            continue

        for row in data:
            nba_id = row.get("PLAYER_ID")
            if nba_id not in player_data:
                player_data[nba_id] = {}
            player_data[nba_id][prefix] = row

    count = 0
    for nba_id, ranges in player_data.items():
        pid = lookup.get(nba_id)
        if not pid:
            continue

        rec = (
            db.query(PlayerDefenderDistanceShooting)
            .filter(
                PlayerDefenderDistanceShooting.player_id == pid,
                PlayerDefenderDistanceShooting.season == season,
            )
            .first()
        )
        if not rec:
            rec = PlayerDefenderDistanceShooting(player_id=pid, season=season)
            db.add(rec)

        for prefix, row in ranges.items():
            # Overall
            setattr(rec, f"{prefix}_fga_freq", _d(row.get("FGA_FREQUENCY")))
            setattr(rec, f"{prefix}_fgm", _d(row.get("FGM")))
            setattr(rec, f"{prefix}_fga", _d(row.get("FGA")))
            setattr(rec, f"{prefix}_fg_pct", _d(row.get("FG_PCT")))
            setattr(rec, f"{prefix}_efg_pct", _d(row.get("EFG_PCT")))
            # 2PT split
            setattr(rec, f"{prefix}_fg2a_freq", _d(row.get("FG2A_FREQUENCY")))
            setattr(rec, f"{prefix}_fg2m", _d(row.get("FG2M")))
            setattr(rec, f"{prefix}_fg2a", _d(row.get("FG2A")))
            setattr(rec, f"{prefix}_fg2_pct", _d(row.get("FG2_PCT")))
            # 3PT split
            setattr(rec, f"{prefix}_fg3a_freq", _d(row.get("FG3A_FREQUENCY")))
            setattr(rec, f"{prefix}_fg3m", _d(row.get("FG3M")))
            setattr(rec, f"{prefix}_fg3a", _d(row.get("FG3A")))
            setattr(rec, f"{prefix}_fg3_pct", _d(row.get("FG3_PCT")))
        count += 1

    print(f"    Stored for {count} players")
    return count


def fetch_defensive_play_types(service: NBADataService, season: str, db: Session, lookup: dict) -> int:
    """Fetch and store defensive Synergy play type data."""
    print("\n  [5/5] Fetching defensive play types (5 API calls)...")

    player_data: dict[int, dict] = {}  # nba_id -> {field_name: row}

    for field_name, api_name in DEF_PLAY_TYPE_FIELDS.items():
        print(f"    Fetching defensive {api_name}...")
        try:
            data = service.get_defensive_synergy_stats(api_name, season)
        except (CircuitBreakerError, RateLimitError) as e:
            print(f"      [ERROR] {e}")
            continue

        for row in data:
            nba_id = row.get("PLAYER_ID")
            if nba_id not in player_data:
                player_data[nba_id] = {}
            player_data[nba_id][field_name] = row

    count = 0
    for nba_id, play_types in player_data.items():
        pid = lookup.get(nba_id)
        if not pid:
            continue

        rec = (
            db.query(PlayerDefensivePlayTypes)
            .filter(
                PlayerDefensivePlayTypes.player_id == pid,
                PlayerDefensivePlayTypes.season == season,
            )
            .first()
        )
        if not rec:
            rec = PlayerDefensivePlayTypes(player_id=pid, season=season)
            db.add(rec)

        total_poss = 0
        for field_name, row in play_types.items():
            poss = row.get("POSS", 0) or 0
            total_poss += poss

            setattr(rec, f"{field_name}_poss", poss)
            setattr(rec, f"{field_name}_pts", row.get("PTS", 0) or 0)
            setattr(rec, f"{field_name}_fgm", row.get("FGM", 0) or 0)
            setattr(rec, f"{field_name}_fga", row.get("FGA", 0) or 0)
            setattr(rec, f"{field_name}_ppp", _d(row.get("PPP")))
            setattr(rec, f"{field_name}_fg_pct", _d(row.get("FG_PCT")))
            setattr(rec, f"{field_name}_tov_pct", _d(row.get("TOV_POSS_PCT")))
            setattr(rec, f"{field_name}_percentile", _d(row.get("PERCENTILE")))

            # Calculate frequency
            if total_poss > 0 and poss > 0:
                setattr(rec, f"{field_name}_freq", _d(poss / total_poss))

        rec.total_poss = total_poss

        # Recalculate frequencies now that total_poss is known
        if total_poss > 0:
            for field_name in play_types:
                poss = getattr(rec, f"{field_name}_poss") or 0
                setattr(rec, f"{field_name}_freq", _d(poss / total_poss))

        count += 1

    print(f"    Stored for {count} players")
    return count


def fetch_and_store_all(
    season: str,
    db: Session,
    verbose: bool = False,
    bypass_cache: bool = False,
) -> bool:
    """Fetch all advanced tracking data and store in database."""
    logger.info("Starting advanced tracking fetch for season %s", season)
    print(f"\nFetching advanced tracking data for season {season}...")
    print(f"  This makes ~12 API calls — expect 2-3 minutes with rate limiting")
    print("-" * 50)

    service = NBADataService(bypass_cache=bypass_cache)
    lookup = _build_nba_id_lookup(db)
    print(f"  Player lookup: {len(lookup)} players")

    totals = {}
    totals["speed_distance"] = fetch_speed_distance(service, season, db, lookup)
    totals["passing"] = fetch_passing(service, season, db, lookup)
    totals["rebounding"] = fetch_rebounding(service, season, db, lookup)
    totals["defender_distance"] = fetch_defender_distance(service, season, db, lookup)
    totals["defensive_play_types"] = fetch_defensive_play_types(service, season, db, lookup)

    try:
        db.commit()
        print(f"\nAll data committed:")
        for name, count in totals.items():
            print(f"  - {name}: {count} players")
        return True
    except Exception as e:
        logger.error("Failed to commit: %s", e)
        db.rollback()
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch advanced tracking data")
    parser.add_argument("--season", default="2024-25")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    print("\n" + "=" * 60)
    print("NBA Advanced Tracking Data Fetcher")
    print("=" * 60)
    print(f"  Season: {args.season}")

    db = SessionLocal()
    try:
        success = fetch_and_store_all(
            args.season, db, verbose=args.verbose, bypass_cache=args.no_cache
        )

        state = nba_api_circuit_breaker.state
        print(f"\nCircuit Breaker Status: {state.value}")

        if success:
            print("\n" + "=" * 60)
            print("Advanced tracking data fetch completed!")
            print("=" * 60 + "\n")
            return 0
        else:
            print("\n[ERROR] Fetch failed!")
            return 1

    except KeyboardInterrupt:
        print("\n\n[INFO] Interrupted by user")
        return 130
    except Exception as e:
        logger.exception("Unexpected error: %s", e)
        print(f"\n[ERROR] {e}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
