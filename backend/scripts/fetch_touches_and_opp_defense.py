#!/usr/bin/env python3
"""Fetch elbow/post/paint touch breakdowns and opponent shooting data.

Populates:
- PlayerTouchesBreakdown  (ElbowTouch, PostTouch, PaintTouch measure types)
- PlayerOpponentShooting  (2 Pointers, Greater Than 15Ft, Less Than 10Ft)

Usage:
    python -m scripts.fetch_touches_and_opp_defense --season 2024-25
"""

import argparse
import logging
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models.opponent_shooting import PlayerOpponentShooting
from app.models.touches_breakdown import PlayerTouchesBreakdown
from app.services.nba_data import NBADataService
from app.services.rate_limiter import (
    CircuitBreakerError,
    RateLimitError,
    nba_api_circuit_breaker,
)
from scripts.shared import build_nba_id_lookup, safe_decimal as _d, setup_logging

logger = logging.getLogger(__name__)


# --- Touch breakdown field mapping ---
# Maps internal field suffix -> NBA API field suffix.
# NBA returns per-game counts with plural "TOUCHES" and per-type stats prefixed
# with {ELBOW,POST,PAINT}_TOUCH_.
TOUCH_METRIC_FIELDS = {
    "fgm": "FGM",
    "fga": "FGA",
    "fg_pct": "FG_PCT",
    "ftm": "FTM",
    "fta": "FTA",
    "ft_pct": "FT_PCT",
    "pts": "PTS",
    "passes": "PASS",
    "ast": "AST",
    "tov": "TOV",
    "fouls": "FOULS",
    "pts_per_touch": "PTS_PER_TOUCH",
}

# (internal prefix, NBA API prefix, count-column-name)
TOUCH_KINDS = (
    ("elbow_touch", "ELBOW_TOUCH", "ELBOW_TOUCHES"),
    ("post_touch", "POST_TOUCH", "POST_TOUCHES"),
    ("paint_touch", "PAINT_TOUCH", "PAINT_TOUCHES"),
)



def _apply_touch_row(
    rec: PlayerTouchesBreakdown,
    internal_prefix: str,
    api_prefix: str,
    count_col: str,
    row: dict,
) -> None:
    """Copy one measure-type row onto the breakdown record."""
    # "elbow_touches"/"post_touches"/"paint_touches"
    setattr(rec, f"{internal_prefix}es", _d(row.get(count_col)))
    for suffix, api_suffix in TOUCH_METRIC_FIELDS.items():
        setattr(
            rec,
            f"{internal_prefix}_{suffix}",
            _d(row.get(f"{api_prefix}_{api_suffix}")),
        )


def fetch_touches_breakdown(
    service: NBADataService, season: str, db: Session, lookup: dict
) -> int:
    """Fetch all three touch breakdowns and upsert into a single row per player."""
    print("\n  [1/2] Fetching elbow / post / paint touches (3 API calls)...")

    # nba_id -> {internal_prefix: row}
    aggregated: dict[int, dict[str, dict]] = {}

    fetchers = {
        "elbow_touch": service.get_elbow_touch_stats,
        "post_touch": service.get_post_touch_stats,
        "paint_touch": service.get_paint_touch_stats,
    }

    for internal_prefix, fetcher in fetchers.items():
        print(f"    Fetching {internal_prefix}...")
        try:
            data = fetcher(season)
        except (CircuitBreakerError, RateLimitError) as exc:
            print(f"      [ERROR] {exc}")
            continue

        for row in data:
            nba_id = row.get("PLAYER_ID")
            if nba_id is None:
                continue
            aggregated.setdefault(nba_id, {})[internal_prefix] = row

    count = 0
    for nba_id, rows_by_kind in aggregated.items():
        pid = lookup.get(nba_id)
        if not pid:
            continue

        rec = (
            db.query(PlayerTouchesBreakdown)
            .filter(
                PlayerTouchesBreakdown.player_id == pid,
                PlayerTouchesBreakdown.season == season,
            )
            .first()
        )
        if not rec:
            rec = PlayerTouchesBreakdown(player_id=pid, season=season)
            db.add(rec)

        for internal_prefix, api_prefix, count_col in TOUCH_KINDS:
            row = rows_by_kind.get(internal_prefix)
            if row is None:
                continue
            _apply_touch_row(rec, internal_prefix, api_prefix, count_col, row)

        count += 1

    print(f"    Stored touch breakdowns for {count} players")
    return count


# --- Opponent shooting mapping ---
# (internal_prefix, fetcher_attr, count_field_for_games_played)
OPP_BUCKETS = (
    ("two_pt", "get_two_point_defense_stats"),
    ("long_mid", "get_long_midrange_defense_stats"),
    ("lt_10ft", "get_less_than_10ft_defense_stats"),
)


def fetch_opponent_shooting(
    service: NBADataService, season: str, db: Session, lookup: dict
) -> int:
    """Fetch 2-point, long-midrange, and <10 ft defense buckets."""
    print("\n  [2/2] Fetching opponent shooting defense (3 API calls)...")

    # nba_id -> {internal_prefix: row}
    aggregated: dict[int, dict[str, dict]] = {}

    for internal_prefix, method_name in OPP_BUCKETS:
        print(f"    Fetching {internal_prefix}...")
        try:
            data = getattr(service, method_name)(season)
        except (CircuitBreakerError, RateLimitError) as exc:
            print(f"      [ERROR] {exc}")
            continue

        for row in data:
            # LeagueDashPtDefend uses CLOSE_DEF_PERSON_ID as the defender ID
            nba_id = row.get("CLOSE_DEF_PERSON_ID") or row.get("PLAYER_ID")
            if nba_id is None:
                continue
            aggregated.setdefault(nba_id, {})[internal_prefix] = row

    count = 0
    for nba_id, rows_by_kind in aggregated.items():
        pid = lookup.get(nba_id)
        if not pid:
            continue

        rec = (
            db.query(PlayerOpponentShooting)
            .filter(
                PlayerOpponentShooting.player_id == pid,
                PlayerOpponentShooting.season == season,
            )
            .first()
        )
        if not rec:
            rec = PlayerOpponentShooting(player_id=pid, season=season)
            db.add(rec)

        # Use 2-point row (the widest sample) to populate defender context
        # fields (age, position, games played).
        two_pt_row = rows_by_kind.get("two_pt")
        if two_pt_row is not None:
            gp = two_pt_row.get("G") or two_pt_row.get("GP")
            rec.two_pt_games = int(gp) if gp is not None else None
            age = two_pt_row.get("AGE")
            try:
                rec.age = int(age) if age is not None else None
            except (TypeError, ValueError):
                rec.age = None
            rec.player_position = two_pt_row.get("PLAYER_POSITION")

        # FREQ is returned per bucket — mirror onto dedicated columns so the
        # frontend can reason about shot-type workload without joining.
        bucket_to_freq_col = {
            "two_pt": "two_pt_freq",
            "long_mid": "long_mid_freq",
            "lt_10ft": "lt_10ft_freq",
        }

        for internal_prefix, _ in OPP_BUCKETS:
            row = rows_by_kind.get(internal_prefix)
            if row is None:
                continue
            setattr(rec, f"{internal_prefix}_defended_fgm", _d(row.get("D_FGM")))
            setattr(rec, f"{internal_prefix}_defended_fga", _d(row.get("D_FGA")))
            setattr(
                rec, f"{internal_prefix}_defended_fg_pct", _d(row.get("D_FG_PCT"))
            )
            setattr(
                rec, f"{internal_prefix}_normal_fg_pct", _d(row.get("NORMAL_FG_PCT"))
            )
            setattr(
                rec, f"{internal_prefix}_pct_plusminus", _d(row.get("PCT_PLUSMINUS"))
            )
            freq_col = bucket_to_freq_col.get(internal_prefix)
            if freq_col is not None:
                setattr(rec, freq_col, _d(row.get("FREQ")))

        count += 1

    print(f"    Stored opponent shooting for {count} players")
    return count


def fetch_and_store_all(
    season: str,
    db: Session,
    verbose: bool = False,
    bypass_cache: bool = False,
) -> bool:
    logger.info("Starting touches / opp-defense fetch for season %s", season)
    print(f"\nFetching touches breakdown & opp shooting for season {season}...")
    print("  This makes 6 API calls — expect ~90s with rate limiting")
    print("-" * 50)

    service = NBADataService(bypass_cache=bypass_cache)
    lookup = build_nba_id_lookup(db)
    print(f"  Player lookup: {len(lookup)} players")

    totals = {
        "touches_breakdown": fetch_touches_breakdown(service, season, db, lookup),
        "opponent_shooting": fetch_opponent_shooting(service, season, db, lookup),
    }

    try:
        db.commit()
        print("\nAll data committed:")
        for name, count in totals.items():
            print(f"  - {name}: {count} players")
        return True
    except Exception as exc:
        logger.error("Failed to commit: %s", exc)
        db.rollback()
        return False


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Fetch touches breakdown and opponent shooting data"
    )
    parser.add_argument("--season", default="2024-25")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    print("\n" + "=" * 60)
    print("Touches Breakdown & Opponent Shooting Fetcher")
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
            print("Fetch completed!")
            print("=" * 60 + "\n")
            return 0
        print("\n[ERROR] Fetch failed!")
        return 1

    except KeyboardInterrupt:
        print("\n\n[INFO] Interrupted by user")
        return 130
    except Exception as exc:
        logger.exception("Unexpected error: %s", exc)
        print(f"\n[ERROR] {exc}")
        return 1
    finally:
        db.close()


if __name__ == "__main__":
    sys.exit(main())
