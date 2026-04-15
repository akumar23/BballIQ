#!/usr/bin/env python3
"""Script to fetch advanced stats, shot zones, clutch stats, and defensive data.

This script fetches:
- Advanced stats (TS%, USG%, NET_RATING, etc.)
- Shot location / zone data
- League shot zone averages
- Clutch time stats
- Defensive stats (overall, rim protection, 3PT defense)
- Isolation defense from Synergy

Usage:
    python -m scripts.fetch_advanced_data --season 2024-25
    python -m scripts.fetch_advanced_data --season 2024-25 --create-tables
    python -m scripts.fetch_advanced_data --season 2024-25 --verbose
    python -m scripts.fetch_advanced_data --from-season 2020-21
    python -m scripts.fetch_advanced_data --seasons 2022-23 2023-24 2024-25
"""

import argparse
import logging
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Player
from app.models.advanced_stats import PlayerAdvancedStats
from app.models.clutch_stats import PlayerClutchStats as PlayerClutchStatsModel
from app.models.defensive_matchups import PlayerDefensiveStats as PlayerDefensiveStatsModel
from app.models.shot_zones import PlayerShotZones as PlayerShotZonesModel
from app.services.nba_data import NBADataService
from app.services.rate_limiter import (
    CircuitBreakerError,
    RateLimitError,
    nba_api_circuit_breaker,
)
from app.services.redis_cache import redis_cache
from scripts.shared import (
    create_tables,
    generate_seasons as generate_season_range,
    safe_decimal,
    safe_int,
    setup_logging,
)

# Configure logging
logger = logging.getLogger(__name__)


def fetch_and_store_advanced_data(
    season: str,
    db: Session,
    verbose: bool = False,
    bypass_cache: bool = False,
) -> bool:
    """Fetch advanced stats, shot zones, clutch, and defensive data.

    Args:
        season: NBA season string (e.g., "2024-25")
        db: Database session
        verbose: If True, print detailed progress
        bypass_cache: If True, skip Redis cache and force API fetch

    Returns:
        True if successful, False otherwise
    """
    logger.info("Starting advanced data fetch for season %s", season)
    print(f"\nFetching advanced data for season {season}...")
    if bypass_cache:
        print("  [INFO] Cache bypass enabled - forcing fresh API calls")
    print("-" * 50)

    service = NBADataService(bypass_cache=bypass_cache)

    # Step 1: Fetch advanced stats
    print("\nStep 1: Fetching advanced stats...")
    try:
        advanced_data = service.get_advanced_stats(season)
        advanced_by_player = {p["PLAYER_ID"]: p for p in advanced_data}
        print(f"  - Fetched advanced stats for {len(advanced_by_player)} players")
        logger.info("Fetched advanced stats for %d players", len(advanced_by_player))
    except (CircuitBreakerError, RateLimitError) as e:
        print(f"  [ERROR] Failed to fetch advanced stats: {e}")
        logger.error("Failed to fetch advanced stats: %s", e)
        return False

    # Step 2: Fetch shot location stats
    print("\nStep 2: Fetching shot location stats...")
    try:
        shot_data = service.get_shot_location_stats(season)
        print(f"  - Fetched shot location data for {len(shot_data)} players")
        logger.info("Fetched shot location data for %d players", len(shot_data))
    except (CircuitBreakerError, RateLimitError) as e:
        print(f"  [ERROR] Failed to fetch shot location stats: {e}")
        logger.error("Failed to fetch shot location stats: %s", e)
        shot_data = []

    # Step 3: Fetch league shot averages
    print("\nStep 3: Fetching league shot averages...")
    try:
        league_averages = service.get_league_shot_averages(season)
        print(f"  - Fetched league shot averages ({len(league_averages)} zones)")
        logger.info("Fetched league shot averages: %d zones", len(league_averages))
    except (CircuitBreakerError, RateLimitError) as e:
        print(f"  [ERROR] Failed to fetch league shot averages: {e}")
        logger.error("Failed to fetch league shot averages: %s", e)
        league_averages = {}

    # Step 4: Fetch clutch stats
    print("\nStep 4: Fetching clutch stats...")
    try:
        clutch_data = service.get_clutch_stats(season)
        clutch_by_player = {p["PLAYER_ID"]: p for p in clutch_data}
        print(f"  - Fetched clutch stats for {len(clutch_by_player)} players")
        logger.info("Fetched clutch stats for %d players", len(clutch_by_player))
    except (CircuitBreakerError, RateLimitError) as e:
        print(f"  [ERROR] Failed to fetch clutch stats: {e}")
        logger.error("Failed to fetch clutch stats: %s", e)
        clutch_by_player = {}

    # Step 5: Fetch defensive stats (overall, rim, 3PT)
    print("\nStep 5: Fetching defensive stats...")

    # Overall defense (already exists in service)
    try:
        overall_defense = service.get_defensive_stats(season)
        overall_def_by_player = {p["CLOSE_DEF_PERSON_ID"]: p for p in overall_defense}
        print(f"  - Fetched overall defensive stats for {len(overall_def_by_player)} players")
        logger.info("Fetched overall defense for %d players", len(overall_def_by_player))
    except (CircuitBreakerError, RateLimitError) as e:
        print(f"  [ERROR] Failed to fetch overall defensive stats: {e}")
        logger.error("Failed to fetch overall defensive stats: %s", e)
        overall_def_by_player = {}

    # Rim protection
    try:
        rim_defense = service.get_rim_protection_stats(season)
        rim_def_by_player = {p["CLOSE_DEF_PERSON_ID"]: p for p in rim_defense}
        print(f"  - Fetched rim protection stats for {len(rim_def_by_player)} players")
        logger.info("Fetched rim protection for %d players", len(rim_def_by_player))
    except Exception as e:
        print(f"  [ERROR] Failed to fetch rim protection stats: {e}")
        logger.error("Failed to fetch rim protection stats: %s", e)
        rim_def_by_player = {}

    # 3PT defense
    try:
        three_pt_defense = service.get_three_point_defense_stats(season)
        three_pt_def_by_player = {p["CLOSE_DEF_PERSON_ID"]: p for p in three_pt_defense}
        print(f"  - Fetched 3PT defensive stats for {len(three_pt_def_by_player)} players")
        logger.info("Fetched 3PT defense for %d players", len(three_pt_def_by_player))
    except Exception as e:
        print(f"  [ERROR] Failed to fetch 3PT defensive stats: {e}")
        logger.error("Failed to fetch 3PT defensive stats: %s", e)
        three_pt_def_by_player = {}

    # Step 6: Fetch isolation defense from Synergy
    print("\nStep 6: Fetching isolation defense stats...")
    try:
        iso_defense = service.get_defensive_play_type_stats("Isolation", season)
        iso_def_by_player = {p["PLAYER_ID"]: p for p in iso_defense}
        print(f"  - Fetched isolation defense for {len(iso_def_by_player)} players")
        logger.info("Fetched isolation defense for %d players", len(iso_def_by_player))
    except Exception as e:
        print(f"  [ERROR] Failed to fetch isolation defense stats: {e}")
        logger.error("Failed to fetch isolation defense stats: %s", e)
        iso_def_by_player = {}

    # Step 7: Store all data in database
    print("\nStep 7: Storing data in database...")

    # Collect all player IDs from all data sources
    all_player_ids = set()
    all_player_ids.update(advanced_by_player.keys())
    all_player_ids.update(clutch_by_player.keys())
    all_player_ids.update(overall_def_by_player.keys())
    all_player_ids.update(rim_def_by_player.keys())
    all_player_ids.update(three_pt_def_by_player.keys())
    all_player_ids.update(iso_def_by_player.keys())

    processed = 0
    errors = 0

    for player_id in all_player_ids:
        try:
            # Match to existing player record
            player = db.query(Player).filter(Player.nba_id == player_id).first()
            if not player:
                logger.debug("Player %d not found in database, skipping", player_id)
                continue

            # Upsert advanced stats
            adv = advanced_by_player.get(player_id)
            if adv:
                adv_stats = (
                    db.query(PlayerAdvancedStats)
                    .filter(
                        PlayerAdvancedStats.player_id == player.id,
                        PlayerAdvancedStats.season == season,
                    )
                    .first()
                )

                if not adv_stats:
                    adv_stats = PlayerAdvancedStats(
                        player_id=player.id,
                        season=season,
                    )
                    db.add(adv_stats)

                adv_stats.ts_pct = safe_decimal(adv.get("TS_PCT"))
                adv_stats.efg_pct = safe_decimal(adv.get("EFG_PCT"))
                adv_stats.usg_pct = safe_decimal(adv.get("USG_PCT"))
                adv_stats.off_rating = safe_decimal(adv.get("OFF_RATING"))
                adv_stats.def_rating = safe_decimal(adv.get("DEF_RATING"))
                adv_stats.net_rating = safe_decimal(adv.get("NET_RATING"))
                adv_stats.pace = safe_decimal(adv.get("PACE"))
                adv_stats.pie = safe_decimal(adv.get("PIE"))
                adv_stats.ast_pct = safe_decimal(adv.get("AST_PCT"))
                adv_stats.ast_to = safe_decimal(adv.get("AST_TO"))
                adv_stats.ast_ratio = safe_decimal(adv.get("AST_RATIO"))
                adv_stats.oreb_pct = safe_decimal(adv.get("OREB_PCT"))
                adv_stats.dreb_pct = safe_decimal(adv.get("DREB_PCT"))
                adv_stats.reb_pct = safe_decimal(adv.get("REB_PCT"))
                adv_stats.tm_tov_pct = safe_decimal(adv.get("TM_TOV_PCT"))
                # Estimated variants + pace/poss from the Advanced measure type
                adv_stats.e_off_rating = safe_decimal(adv.get("E_OFF_RATING"))
                adv_stats.e_def_rating = safe_decimal(adv.get("E_DEF_RATING"))
                adv_stats.e_net_rating = safe_decimal(adv.get("E_NET_RATING"))
                adv_stats.e_usg_pct = safe_decimal(adv.get("E_USG_PCT"))
                adv_stats.e_pace = safe_decimal(adv.get("E_PACE"))
                adv_stats.pace_per40 = safe_decimal(adv.get("PACE_PER40"))
                adv_stats.poss = safe_int(adv.get("POSS"))

            # Upsert clutch stats
            clutch = clutch_by_player.get(player_id)
            if clutch:
                clutch_stats = (
                    db.query(PlayerClutchStatsModel)
                    .filter(
                        PlayerClutchStatsModel.player_id == player.id,
                        PlayerClutchStatsModel.season == season,
                    )
                    .first()
                )

                if not clutch_stats:
                    clutch_stats = PlayerClutchStatsModel(
                        player_id=player.id,
                        season=season,
                    )
                    db.add(clutch_stats)

                clutch_stats.games_played = safe_int(clutch.get("GP"))
                clutch_stats.minutes = safe_decimal(clutch.get("MIN"))
                clutch_stats.pts = safe_decimal(clutch.get("PTS"))
                clutch_stats.fgm = safe_decimal(clutch.get("FGM"))
                clutch_stats.fga = safe_decimal(clutch.get("FGA"))
                clutch_stats.fg_pct = safe_decimal(clutch.get("FG_PCT"))
                clutch_stats.fg3m = safe_decimal(clutch.get("FG3M"))
                clutch_stats.fg3a = safe_decimal(clutch.get("FG3A"))
                clutch_stats.fg3_pct = safe_decimal(clutch.get("FG3_PCT"))
                clutch_stats.ftm = safe_decimal(clutch.get("FTM"))
                clutch_stats.fta = safe_decimal(clutch.get("FTA"))
                clutch_stats.ft_pct = safe_decimal(clutch.get("FT_PCT"))
                clutch_stats.ast = safe_decimal(clutch.get("AST"))
                clutch_stats.reb = safe_decimal(clutch.get("REB"))
                clutch_stats.stl = safe_decimal(clutch.get("STL"))
                clutch_stats.blk = safe_decimal(clutch.get("BLK"))
                clutch_stats.tov = safe_decimal(clutch.get("TOV"))
                clutch_stats.plus_minus = safe_decimal(clutch.get("PLUS_MINUS"))
                clutch_stats.net_rating = safe_decimal(clutch.get("NET_RATING"))

            # Upsert defensive stats (overall + rim + 3PT + iso)
            overall = overall_def_by_player.get(player_id)
            rim = rim_def_by_player.get(player_id)
            three_pt = three_pt_def_by_player.get(player_id)
            iso = iso_def_by_player.get(player_id)

            if overall or rim or three_pt or iso:
                def_stats = (
                    db.query(PlayerDefensiveStatsModel)
                    .filter(
                        PlayerDefensiveStatsModel.player_id == player.id,
                        PlayerDefensiveStatsModel.season == season,
                    )
                    .first()
                )

                if not def_stats:
                    def_stats = PlayerDefensiveStatsModel(
                        player_id=player.id,
                        season=season,
                    )
                    db.add(def_stats)

                if overall:
                    # Defender context — overall row has the widest GP sample
                    def_stats.games_played = safe_int(overall.get("GP"))
                    def_stats.age = safe_int(overall.get("AGE"))
                    def_stats.overall_d_fgm = safe_decimal(overall.get("D_FGM"))
                    def_stats.overall_d_fga = safe_decimal(overall.get("D_FGA"))
                    def_stats.overall_d_fg_pct = safe_decimal(overall.get("D_FG_PCT"))
                    def_stats.overall_normal_fg_pct = safe_decimal(overall.get("NORMAL_FG_PCT"))
                    def_stats.overall_pct_plusminus = safe_decimal(overall.get("PCT_PLUSMINUS"))
                    def_stats.overall_freq = safe_decimal(overall.get("FREQ"))

                if rim:
                    def_stats.rim_d_fgm = safe_decimal(rim.get("FGM_LT_06"))
                    def_stats.rim_d_fga = safe_decimal(rim.get("FGA_LT_06"))
                    def_stats.rim_d_fg_pct = safe_decimal(rim.get("LT_06_PCT"))
                    def_stats.rim_normal_fg_pct = safe_decimal(rim.get("NS_LT_06_PCT"))
                    def_stats.rim_pct_plusminus = safe_decimal(rim.get("PLUSMINUS"))
                    def_stats.rim_freq = safe_decimal(rim.get("FREQ"))

                if three_pt:
                    def_stats.three_pt_d_fgm = safe_decimal(three_pt.get("FG3M"))
                    def_stats.three_pt_d_fga = safe_decimal(three_pt.get("FG3A"))
                    def_stats.three_pt_d_fg_pct = safe_decimal(three_pt.get("FG3_PCT"))
                    def_stats.three_pt_normal_fg_pct = safe_decimal(three_pt.get("NS_FG3_PCT"))
                    def_stats.three_pt_pct_plusminus = safe_decimal(three_pt.get("PLUSMINUS"))
                    def_stats.three_pt_freq = safe_decimal(three_pt.get("FREQ"))

                if iso:
                    def_stats.iso_poss = safe_int(iso.get("POSS"))
                    def_stats.iso_pts = safe_int(iso.get("PTS"))
                    def_stats.iso_fgm = safe_int(iso.get("FGM"))
                    def_stats.iso_fga = safe_int(iso.get("FGA"))
                    def_stats.iso_ppp = safe_decimal(iso.get("PPP"))
                    def_stats.iso_fg_pct = safe_decimal(iso.get("FG_PCT"))
                    def_stats.iso_percentile = safe_decimal(iso.get("PERCENTILE"))

            processed += 1

            if verbose and processed % 50 == 0:
                print(f"  Processed {processed} players...")

        except Exception as e:
            logger.error("Error processing player %d: %s", player_id, e)
            errors += 1

    # Step 8: Store shot zone data
    print("\nStep 8: Storing shot zone data...")
    shot_processed = 0

    # Build league average lookup
    league_avg_lookup = {}
    if isinstance(league_averages, list):
        for zone_data in league_averages:
            zone_name = zone_data.get("ZONE_NAME") or zone_data.get("SHOT_ZONE_BASIC")
            if zone_name:
                league_avg_lookup[zone_name] = safe_decimal(zone_data.get("FG_PCT"))
    elif isinstance(league_averages, dict):
        league_avg_lookup = {k: safe_decimal(v) for k, v in league_averages.items()}

    # The NBA API's LeagueDashPlayerShotLocations returns data with
    # nested/tuple column headers: (zone_name, stat_name) e.g.
    # ('Restricted Area', 'FGM'), ('', 'PLAYER_ID'). Flatten each
    # player row into multiple per-zone records for storage.
    def _flatten_shot_data(shot_data: list[dict]) -> list[dict]:
        """Convert nested per-player shot data into per-zone records."""
        flat_records = []
        for row in shot_data:
            # Extract player ID from tuple or flat key
            player_id = None
            for key, val in row.items():
                if isinstance(key, tuple):
                    if key[1] == "PLAYER_ID" or str(key[1]) == "PLAYER_ID":
                        player_id = val
                        break
                elif key == "PLAYER_ID":
                    player_id = val
                    break

            if not player_id:
                continue

            # Collect zone data from tuple keys
            zones: dict[str, dict] = {}
            total_fga = Decimal(0)
            for key, val in row.items():
                if not isinstance(key, tuple) or len(key) != 2:
                    continue
                zone_name, stat_name = str(key[0]), str(key[1])
                if not zone_name:  # Skip metadata columns like ('', 'PLAYER_ID')
                    continue
                if zone_name not in zones:
                    zones[zone_name] = {"PLAYER_ID": player_id, "ZONE_NAME": zone_name}
                zones[zone_name][stat_name] = val
                if stat_name == "FGA" and val is not None:
                    total_fga += Decimal(str(val))

            for zone_name, zone_dict in zones.items():
                zone_dict["TOTAL_FGA"] = total_fga
                flat_records.append(zone_dict)

        return flat_records

    # Check if data has tuple keys (nested format) or flat keys
    if shot_data and any(isinstance(k, tuple) for k in shot_data[0].keys()):
        shot_records = _flatten_shot_data(shot_data)
        logger.info("Flattened %d players into %d zone records", len(shot_data), len(shot_records))
    else:
        shot_records = shot_data

    for shot_row in shot_records:
        try:
            player_id = shot_row.get("PLAYER_ID")
            if not player_id:
                continue

            player = db.query(Player).filter(Player.nba_id == player_id).first()
            if not player:
                continue

            zone_name = shot_row.get("ZONE_NAME") or shot_row.get("SHOT_ZONE_BASIC", "Unknown")
            fgm = safe_decimal(shot_row.get("FGM"))
            fga = safe_decimal(shot_row.get("FGA"))
            fg_pct = safe_decimal(shot_row.get("FG_PCT"))

            # Calculate frequency if total FGA is available
            total_fga = safe_decimal(shot_row.get("TOTAL_FGA"))
            freq = None
            try:
                if total_fga and total_fga > 0 and fga is not None:
                    freq = fga / total_fga
            except Exception:
                freq = None

            # Look up league average for this zone
            league_avg = league_avg_lookup.get(zone_name)

            # Upsert shot zone record
            existing = (
                db.query(PlayerShotZonesModel)
                .filter(
                    PlayerShotZonesModel.player_id == player.id,
                    PlayerShotZonesModel.season == season,
                    PlayerShotZonesModel.zone == zone_name,
                )
                .first()
            )

            if not existing:
                existing = PlayerShotZonesModel(
                    player_id=player.id,
                    season=season,
                    zone=zone_name,
                )
                db.add(existing)

            existing.fgm = fgm
            existing.fga = fga
            existing.fg_pct = fg_pct
            existing.freq = freq
            existing.league_avg = league_avg

            shot_processed += 1

        except Exception as e:
            logger.error("Error processing shot zone data: %s", e)
            errors += 1

    print(f"  - Processed {shot_processed} shot zone records")

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
        print(f"  [WARNING] {errors} records had processing errors")
        logger.warning("%d records had processing errors", errors)

    return True


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
        description="Fetch advanced stats, shot zones, clutch, and defensive data",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m scripts.fetch_advanced_data --season 2024-25
    python -m scripts.fetch_advanced_data --season 2024-25 --create-tables
    python -m scripts.fetch_advanced_data --season 2024-25 --verbose
    python -m scripts.fetch_advanced_data --season 2024-25 --no-cache
    python -m scripts.fetch_advanced_data --from-season 2020-21
    python -m scripts.fetch_advanced_data --from-season 2020-21 --season 2024-25
    python -m scripts.fetch_advanced_data --seasons 2022-23 2023-24 2024-25
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
    args = parser.parse_args()

    setup_logging(args.verbose)

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

    print("\n" + "=" * 60)
    print("StatFloor Advanced Stats Data Fetcher")
    print("=" * 60)

    print(f"\nConfiguration:")
    print(f"  Seasons: {', '.join(seasons_to_fetch)}")
    print(f"  Cache bypass: {args.no_cache}")
    print(f"\n  NOTE: This script makes ~7 API calls per season")
    print(f"        Expected runtime: 1-2 minutes per season with rate limiting")

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

            success = fetch_and_store_advanced_data(
                season, db, verbose=args.verbose, bypass_cache=args.no_cache
            )

            if not success:
                failed_seasons.append(season)
                logger.error("Failed to fetch advanced data for season %s", season)

        print_circuit_breaker_status()
        print_cache_status()

        if not failed_seasons:
            print("\n" + "=" * 60)
            seasons_label = ", ".join(seasons_to_fetch)
            print(f"Advanced data fetch completed successfully! ({seasons_label})")
            print("=" * 60 + "\n")
            return 0
        else:
            print("\n" + "=" * 60)
            print(f"[ERROR] Advanced data fetch failed for: {', '.join(failed_seasons)}")
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
