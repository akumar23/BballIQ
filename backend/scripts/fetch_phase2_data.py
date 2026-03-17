#!/usr/bin/env python3
"""Script to fetch Phase 2 data: shooting tracking, computed metrics, and career stats.

This script handles three parts:
  Part A - Fetch raw data from NBA API (team stats, per-100, shooting tracking)
  Part B - Compute derived metrics (PER, BPM, Win Shares, Radar)
  Part C - Fetch career stats for top players

Usage:
    python -m scripts.fetch_phase2_data --season 2024-25
    python -m scripts.fetch_phase2_data --season 2024-25 --create-tables
    python -m scripts.fetch_phase2_data --season 2024-25 --career-limit 50
    python -m scripts.fetch_phase2_data --season 2024-25 --verbose
"""

import argparse
import logging
import sys
import time
from decimal import Decimal
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy import desc
from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Player
from app.models.advanced_stats import PlayerAdvancedStats
from app.models.career_stats import PlayerCareerStats as PlayerCareerStatsModel
from app.models.clutch_stats import PlayerClutchStats as PlayerClutchStatsModel
from app.models.computed_advanced import PlayerComputedAdvanced
from app.models.defensive_matchups import PlayerDefensiveStats as PlayerDefensiveStatsModel
from app.models.season_play_type_stats import SeasonPlayTypeStats
from app.models.season_stats import SeasonStats
from app.models.shooting_tracking import PlayerShootingTracking
from app.services.nba_data import NBADataService
from app.services.rate_limiter import (
    CircuitBreakerError,
    RateLimitError,
    nba_api_circuit_breaker,
)
from app.services.redis_cache import redis_cache


# Configure logging
logger = logging.getLogger(__name__)

# Play type fields for diversity calculation
PLAY_TYPE_FREQ_FIELDS = [
    "isolation_freq",
    "pnr_ball_handler_freq",
    "pnr_roll_man_freq",
    "post_up_freq",
    "spot_up_freq",
    "transition_freq",
    "cut_freq",
    "off_screen_freq",
]

# Frequency threshold for counting a play type as "used"
FREQ_THRESHOLD = Decimal("0.05")


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


def safe_decimal(value, default=None) -> Decimal | None:
    """Safely convert a value to Decimal, returning default on failure.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        Decimal value or default
    """
    if value is None:
        return default
    try:
        return Decimal(str(value))
    except Exception:
        return default


def safe_int(value, default=None) -> int | None:
    """Safely convert a value to int, returning default on failure.

    Args:
        value: Value to convert
        default: Default value if conversion fails

    Returns:
        int value or default
    """
    if value is None:
        return default
    try:
        return int(value)
    except (ValueError, TypeError):
        return default


def fetch_and_store_shooting_tracking(
    season: str,
    db: Session,
    service: NBADataService,
    verbose: bool = False,
) -> dict:
    """Part A: Fetch shooting tracking data and store in database.

    Fetches catch-and-shoot, pull-up, and drive stats from NBA API
    and stores them in PlayerShootingTracking.

    Args:
        season: NBA season string
        db: Database session
        service: NBADataService instance
        verbose: If True, print detailed progress

    Returns:
        Dict with status and counts
    """
    print("\n--- Part A: Fetching Shooting Tracking Data ---")
    errors = 0
    processed = 0

    # Step 1: Fetch catch-and-shoot stats
    print("\nStep 1: Fetching catch-and-shoot stats...")
    try:
        catch_shoot_data = service.get_catch_shoot_stats(season)
        catch_shoot_by_player = {p["PLAYER_ID"]: p for p in catch_shoot_data}
        print(f"  - Fetched catch-shoot stats for {len(catch_shoot_by_player)} players")
        logger.info("Fetched catch-shoot stats for %d players", len(catch_shoot_by_player))
    except (CircuitBreakerError, RateLimitError) as e:
        print(f"  [ERROR] Failed to fetch catch-shoot stats: {e}")
        logger.error("Failed to fetch catch-shoot stats: %s", e)
        catch_shoot_by_player = {}

    # Step 2: Fetch pull-up stats
    print("\nStep 2: Fetching pull-up stats...")
    try:
        pullup_data = service.get_pullup_stats(season)
        pullup_by_player = {p["PLAYER_ID"]: p for p in pullup_data}
        print(f"  - Fetched pull-up stats for {len(pullup_by_player)} players")
        logger.info("Fetched pull-up stats for %d players", len(pullup_by_player))
    except (CircuitBreakerError, RateLimitError) as e:
        print(f"  [ERROR] Failed to fetch pull-up stats: {e}")
        logger.error("Failed to fetch pull-up stats: %s", e)
        pullup_by_player = {}

    # Step 3: Fetch drive stats
    print("\nStep 3: Fetching drive stats...")
    try:
        drive_data = service.get_drive_stats(season)
        drive_by_player = {p["PLAYER_ID"]: p for p in drive_data}
        print(f"  - Fetched drive stats for {len(drive_by_player)} players")
        logger.info("Fetched drive stats for %d players", len(drive_by_player))
    except (CircuitBreakerError, RateLimitError) as e:
        print(f"  [ERROR] Failed to fetch drive stats: {e}")
        logger.error("Failed to fetch drive stats: %s", e)
        drive_by_player = {}

    # Step 4: Store shooting tracking data
    print("\nStep 4: Storing shooting tracking data...")

    all_player_ids = set()
    all_player_ids.update(catch_shoot_by_player.keys())
    all_player_ids.update(pullup_by_player.keys())
    all_player_ids.update(drive_by_player.keys())

    for player_id in all_player_ids:
        try:
            player = db.query(Player).filter(Player.nba_id == player_id).first()
            if not player:
                continue

            cs = catch_shoot_by_player.get(player_id)
            pu = pullup_by_player.get(player_id)
            dr = drive_by_player.get(player_id)

            # Upsert shooting tracking record
            tracking = (
                db.query(PlayerShootingTracking)
                .filter(
                    PlayerShootingTracking.player_id == player.id,
                    PlayerShootingTracking.season == season,
                )
                .first()
            )

            if not tracking:
                tracking = PlayerShootingTracking(
                    player_id=player.id,
                    season=season,
                )
                db.add(tracking)

            # Catch-and-shoot
            if cs:
                tracking.catch_shoot_fgm = safe_decimal(cs.get("FGM"))
                tracking.catch_shoot_fga = safe_decimal(cs.get("FGA"))
                tracking.catch_shoot_fg_pct = safe_decimal(cs.get("FG_PCT"))
                tracking.catch_shoot_fg3m = safe_decimal(cs.get("FG3M"))
                tracking.catch_shoot_fg3a = safe_decimal(cs.get("FG3A"))
                tracking.catch_shoot_fg3_pct = safe_decimal(cs.get("FG3_PCT"))
                tracking.catch_shoot_pts = safe_decimal(cs.get("PTS"))
                tracking.catch_shoot_efg_pct = safe_decimal(cs.get("EFG_PCT"))

            # Pull-up
            if pu:
                tracking.pullup_fgm = safe_decimal(pu.get("FGM"))
                tracking.pullup_fga = safe_decimal(pu.get("FGA"))
                tracking.pullup_fg_pct = safe_decimal(pu.get("FG_PCT"))
                tracking.pullup_fg3m = safe_decimal(pu.get("FG3M"))
                tracking.pullup_fg3a = safe_decimal(pu.get("FG3A"))
                tracking.pullup_fg3_pct = safe_decimal(pu.get("FG3_PCT"))
                tracking.pullup_pts = safe_decimal(pu.get("PTS"))
                tracking.pullup_efg_pct = safe_decimal(pu.get("EFG_PCT"))

            # Drives
            if dr:
                tracking.drives = safe_decimal(dr.get("DRIVES"))
                tracking.drive_fgm = safe_decimal(dr.get("DRIVE_FGM"))
                tracking.drive_fga = safe_decimal(dr.get("DRIVE_FGA"))
                tracking.drive_fg_pct = safe_decimal(dr.get("DRIVE_FG_PCT"))
                tracking.drive_pts = safe_decimal(dr.get("DRIVE_PTS"))
                tracking.drive_ast = safe_decimal(dr.get("DRIVE_AST"))
                tracking.drive_tov = safe_decimal(dr.get("DRIVE_TOV"))

            processed += 1

            if verbose and processed % 50 == 0:
                print(f"  Processed {processed} players...")

        except Exception as e:
            logger.error("Error processing shooting tracking for player %d: %s", player_id, e)
            errors += 1

    try:
        db.commit()
        print(f"  - Stored shooting tracking for {processed} players")
        logger.info("Stored shooting tracking for %d players", processed)
    except Exception as e:
        logger.error("Failed to commit shooting tracking: %s", e)
        db.rollback()
        return {"status": "error", "message": str(e)}

    return {"status": "success", "processed": processed, "errors": errors}


def compute_and_store_metrics(
    season: str,
    db: Session,
    service: NBADataService,
    verbose: bool = False,
) -> dict:
    """Part B: Compute PER, BPM, Win Shares, Radar and store in database.

    Loads raw data from DB and NBA API, runs calculators, and stores
    results in PlayerComputedAdvanced.

    Args:
        season: NBA season string
        db: Database session
        service: NBADataService instance
        verbose: If True, print detailed progress

    Returns:
        Dict with status and counts
    """
    from app.services.bpm_calculator import BPMCalculator, PlayerBPMInput
    from app.services.per_calculator import (
        LeagueStats,
        PERCalculator,
        PlayerPERData,
        TeamStats,
    )
    from app.services.radar_calculator import RadarCalculator, RadarInput
    from app.services.win_shares_calculator import (
        WinSharesCalculator,
        WinSharesInput,
    )

    print("\n--- Part B: Computing Advanced Metrics ---")
    errors = 0

    # Step 1: Fetch team stats from NBA API (needed for PER and Win Shares)
    print("\nStep 1: Fetching team stats...")
    try:
        team_base_data = service.get_team_stats(season, "Base")
        team_base_by_id = {t["TEAM_ID"]: t for t in team_base_data}
        team_base_by_abbr = {t["TEAM_ABBREVIATION"]: t for t in team_base_data}
        print(f"  - Fetched base team stats for {len(team_base_by_id)} teams")
    except (CircuitBreakerError, RateLimitError) as e:
        print(f"  [ERROR] Failed to fetch team base stats: {e}")
        logger.error("Failed to fetch team base stats: %s", e)
        return {"status": "error", "message": str(e)}

    try:
        team_adv_data = service.get_team_stats(season, "Advanced")
        team_adv_by_abbr = {t["TEAM_ABBREVIATION"]: t for t in team_adv_data}
        print(f"  - Fetched advanced team stats for {len(team_adv_by_abbr)} teams")
    except (CircuitBreakerError, RateLimitError) as e:
        print(f"  [ERROR] Failed to fetch team advanced stats: {e}")
        logger.error("Failed to fetch team advanced stats: %s", e)
        return {"status": "error", "message": str(e)}

    # Step 2: Fetch per-100 possession stats
    print("\nStep 2: Fetching per-100 possession stats...")
    try:
        per100_data = service.get_per100_stats(season)
        per100_by_player_id = {p["PLAYER_ID"]: p for p in per100_data}
        print(f"  - Fetched per-100 stats for {len(per100_by_player_id)} players")
    except (CircuitBreakerError, RateLimitError) as e:
        print(f"  [ERROR] Failed to fetch per-100 stats: {e}")
        logger.error("Failed to fetch per-100 stats: %s", e)
        per100_by_player_id = {}

    # Step 3: Load existing data from DB
    print("\nStep 3: Loading data from database...")

    # Load all players with season stats
    season_stats_rows = (
        db.query(SeasonStats, Player)
        .join(Player, Player.id == SeasonStats.player_id)
        .filter(
            SeasonStats.season == season,
            SeasonStats.total_minutes.isnot(None),
            SeasonStats.total_minutes > 0,
        )
        .all()
    )
    print(f"  - Loaded {len(season_stats_rows)} season stats records")

    # Build lookup by nba_id
    season_stats_by_nba_id: dict[int, tuple[SeasonStats, Player]] = {}
    for ss, player in season_stats_rows:
        season_stats_by_nba_id[player.nba_id] = (ss, player)

    # Load advanced stats
    advanced_stats_rows = (
        db.query(PlayerAdvancedStats, Player)
        .join(Player, Player.id == PlayerAdvancedStats.player_id)
        .filter(PlayerAdvancedStats.season == season)
        .all()
    )
    advanced_by_nba_id: dict[int, PlayerAdvancedStats] = {
        player.nba_id: adv for adv, player in advanced_stats_rows
    }
    print(f"  - Loaded {len(advanced_by_nba_id)} advanced stats records")

    # Load clutch stats
    clutch_stats_rows = (
        db.query(PlayerClutchStatsModel, Player)
        .join(Player, Player.id == PlayerClutchStatsModel.player_id)
        .filter(PlayerClutchStatsModel.season == season)
        .all()
    )
    clutch_by_nba_id: dict[int, PlayerClutchStatsModel] = {
        player.nba_id: clutch for clutch, player in clutch_stats_rows
    }
    print(f"  - Loaded {len(clutch_by_nba_id)} clutch stats records")

    # Load defensive stats
    defensive_stats_rows = (
        db.query(PlayerDefensiveStatsModel, Player)
        .join(Player, Player.id == PlayerDefensiveStatsModel.player_id)
        .filter(PlayerDefensiveStatsModel.season == season)
        .all()
    )
    defensive_by_nba_id: dict[int, PlayerDefensiveStatsModel] = {
        player.nba_id: defense for defense, player in defensive_stats_rows
    }
    print(f"  - Loaded {len(defensive_by_nba_id)} defensive stats records")

    # Load play type stats
    play_type_rows = (
        db.query(SeasonPlayTypeStats, Player)
        .join(Player, Player.id == SeasonPlayTypeStats.player_id)
        .filter(SeasonPlayTypeStats.season == season)
        .all()
    )
    play_type_by_nba_id: dict[int, SeasonPlayTypeStats] = {
        player.nba_id: pt for pt, player in play_type_rows
    }
    print(f"  - Loaded {len(play_type_by_nba_id)} play type stats records")

    # --- Step 4: Build calculator inputs and run PER ---
    print("\nStep 4: Calculating PER...")

    # Build league and team stats for PER calculator
    # Aggregate league totals from team base stats
    lg_ast = sum(t.get("AST", 0) or 0 for t in team_base_data)
    lg_fgm = sum(t.get("FGM", 0) or 0 for t in team_base_data)
    lg_ftm = sum(t.get("FTM", 0) or 0 for t in team_base_data)
    lg_fta = sum(t.get("FTA", 0) or 0 for t in team_base_data)
    lg_pts = sum(t.get("PTS", 0) or 0 for t in team_base_data)
    lg_fga = sum(t.get("FGA", 0) or 0 for t in team_base_data)
    lg_orb = sum(t.get("OREB", 0) or 0 for t in team_base_data)
    lg_trb = sum(t.get("REB", 0) or 0 for t in team_base_data)
    lg_tov = sum(t.get("TOV", 0) or 0 for t in team_base_data)
    lg_pf = sum(t.get("PF", 0) or 0 for t in team_base_data)

    # Average pace from team advanced stats
    team_paces = [Decimal(str(t.get("PACE", 0) or 0)) for t in team_adv_data]
    lg_pace = sum(team_paces) / Decimal(len(team_paces)) if team_paces else Decimal("100")

    league_stats = LeagueStats(
        ast=lg_ast,
        fgm=lg_fgm,
        ftm=lg_ftm,
        fta=lg_fta,
        pts=lg_pts,
        fga=lg_fga,
        orb=lg_orb,
        trb=lg_trb,
        tov=lg_tov,
        pf=lg_pf,
        pace=lg_pace,
    )

    # Build team stats dict
    per_team_stats: dict[str, TeamStats] = {}
    for t in team_base_data:
        abbr = t["TEAM_ABBREVIATION"]
        adv = team_adv_by_abbr.get(abbr, {})
        per_team_stats[abbr] = TeamStats(
            team_id=t.get("TEAM_ID", 0),
            team_abbreviation=abbr,
            games_played=t.get("GP", 0) or 0,
            minutes=Decimal(str(t.get("MIN", 0) or 0)),
            fgm=t.get("FGM", 0) or 0,
            fga=t.get("FGA", 0) or 0,
            fg3m=t.get("FG3M", 0) or 0,
            ast=t.get("AST", 0) or 0,
            ftm=t.get("FTM", 0) or 0,
            fta=t.get("FTA", 0) or 0,
            orb=t.get("OREB", 0) or 0,
            trb=t.get("REB", 0) or 0,
            tov=t.get("TOV", 0) or 0,
            pf=t.get("PF", 0) or 0,
            pts=t.get("PTS", 0) or 0,
            pace=Decimal(str(adv.get("PACE", 100) or 100)),
        )

    # Build PER player inputs from season stats
    per_players: list[PlayerPERData] = []
    for nba_id, (ss, player) in season_stats_by_nba_id.items():
        if ss.total_minutes is None or ss.total_minutes < 100:
            continue
        per_players.append(
            PlayerPERData(
                player_id=nba_id,
                team_abbreviation=player.team_abbreviation or "",
                minutes=ss.total_minutes,
                fg3m=ss.total_fg3m or 0,
                ast=ss.total_assists or 0,
                fgm=ss.total_fgm or 0,
                ftm=ss.total_ftm or 0,
                fta=ss.total_fta or 0,
                fga=ss.total_fga or 0,
                tov=ss.total_turnovers or 0,
                orb=ss.total_offensive_rebounds or 0,
                drb=ss.total_defensive_rebounds or 0,
                trb=ss.total_rebounds or 0,
                stl=ss.total_steals or 0,
                blk=ss.total_blocks or 0,
                pf=0,  # PF not tracked in season_stats; set to 0
                pts=ss.total_points or 0,
            )
        )

    per_calculator = PERCalculator(league_stats, per_team_stats)
    per_results = per_calculator.calculate_all(per_players)
    print(f"  - Calculated PER for {len(per_results)} players")

    # --- Step 5: Calculate BPM ---
    print("\nStep 5: Calculating BPM...")

    bpm_players: list[PlayerBPMInput] = []
    for nba_id, (ss, player) in season_stats_by_nba_id.items():
        if ss.total_minutes is None or ss.total_minutes < 100:
            continue

        per100 = per100_by_player_id.get(nba_id)
        adv = advanced_by_nba_id.get(nba_id)
        team_abbr = player.team_abbreviation or ""
        team_adv = team_adv_by_abbr.get(team_abbr, {})

        if not per100:
            continue

        bpm_players.append(
            PlayerBPMInput(
                player_id=nba_id,
                team_abbreviation=team_abbr,
                position=player.position or "F",
                minutes=ss.total_minutes,
                games_played=ss.games_played or 0,
                pts_per100=Decimal(str(per100.get("PTS", 0) or 0)),
                trb_per100=Decimal(str(per100.get("REB", 0) or 0)),
                ast_per100=Decimal(str(per100.get("AST", 0) or 0)),
                stl_per100=Decimal(str(per100.get("STL", 0) or 0)),
                blk_per100=Decimal(str(per100.get("BLK", 0) or 0)),
                tov_per100=Decimal(str(per100.get("TOV", 0) or 0)),
                ts_pct=Decimal(str(adv.ts_pct or 0)) if adv else Decimal("0"),
                usg_pct=Decimal(str(adv.usg_pct or 0)) if adv else Decimal("0"),
                team_net_rating=Decimal(str(team_adv.get("NET_RATING", 0) or 0)),
            )
        )

    bpm_calculator = BPMCalculator()
    bpm_results = bpm_calculator.calculate_all(bpm_players)
    print(f"  - Calculated BPM for {len(bpm_results)} players")

    # --- Step 6: Calculate Win Shares ---
    print("\nStep 6: Calculating Win Shares...")

    # League averages for Win Shares
    total_team_games = sum(t.get("GP", 0) or 0 for t in team_base_data)
    lg_ppg = Decimal(str(lg_pts)) / Decimal(total_team_games) if total_team_games > 0 else Decimal("112")
    lg_ppp = Decimal(str(lg_pts)) / (Decimal(str(lg_fga)) - Decimal(str(lg_orb)) + Decimal(str(lg_tov)) + Decimal("0.44") * Decimal(str(lg_fta))) if lg_fga > 0 else Decimal("1.12")

    ws_calculator = WinSharesCalculator(
        league_ppg=lg_ppg,
        league_pace=lg_pace,
        league_ppp=lg_ppp,
    )

    ws_players: list[WinSharesInput] = []
    for nba_id, (ss, player) in season_stats_by_nba_id.items():
        if ss.total_minutes is None or ss.total_minutes < 100:
            continue

        adv = advanced_by_nba_id.get(nba_id)
        if not adv or adv.off_rating is None or adv.def_rating is None:
            continue

        team_abbr = player.team_abbreviation or ""
        team_base = team_base_by_abbr.get(team_abbr, {})
        team_adv = team_adv_by_abbr.get(team_abbr, {})
        team_minutes = Decimal(str(team_base.get("MIN", 0) or 0))
        team_pace = Decimal(str(team_adv.get("PACE", 100) or 100))
        team_gp = team_base.get("GP", 0) or 0

        # Estimate team defensive possessions
        team_def_poss = team_pace * Decimal(team_gp)

        ws_players.append(
            WinSharesInput(
                player_id=nba_id,
                team_abbreviation=team_abbr,
                minutes=ss.total_minutes,
                off_rating=adv.off_rating,
                def_rating=adv.def_rating,
                team_minutes=team_minutes,
                team_pace=team_pace,
                team_def_possessions=team_def_poss,
            )
        )

    ws_results = ws_calculator.calculate_all(ws_players)
    print(f"  - Calculated Win Shares for {len(ws_results)} players")

    # --- Step 7: Calculate Radar ---
    print("\nStep 7: Calculating Radar percentiles...")

    radar_players: list[RadarInput] = []
    for nba_id, (ss, player) in season_stats_by_nba_id.items():
        if ss.total_minutes is None or ss.total_minutes < 100 or ss.games_played is None or ss.games_played == 0:
            continue

        adv = advanced_by_nba_id.get(nba_id)
        clutch = clutch_by_nba_id.get(nba_id)
        defense = defensive_by_nba_id.get(nba_id)
        play_type = play_type_by_nba_id.get(nba_id)

        gp = ss.games_played
        mpg = ss.total_minutes / Decimal(gp)
        ppg = Decimal(ss.total_points or 0) / Decimal(gp)
        apg = Decimal(ss.total_assists or 0) / Decimal(gp)
        spg = Decimal(ss.total_steals or 0) / Decimal(gp)
        bpg = Decimal(ss.total_blocks or 0) / Decimal(gp)
        tov_pg = Decimal(ss.total_turnovers or 0) / Decimal(gp)
        fga_pg = Decimal(ss.total_fga or 0) / Decimal(gp)
        defl_pg = Decimal(ss.total_deflections or 0) / Decimal(gp) if ss.total_deflections else Decimal("0")

        # DFG% differential from defensive stats (can be None)
        dfg_diff = None
        if defense and defense.overall_pct_plusminus is not None:
            dfg_diff = defense.overall_pct_plusminus

        # Play type diversity: count play types with >5% frequency
        play_type_count = 0
        if play_type:
            for field in PLAY_TYPE_FREQ_FIELDS:
                freq = getattr(play_type, field, None)
                if freq is not None and freq >= FREQ_THRESHOLD:
                    play_type_count += 1

        # Clutch stats
        clutch_pts = Decimal(str(clutch.pts)) if clutch and clutch.pts is not None else None
        clutch_pm = Decimal(str(clutch.plus_minus)) if clutch and clutch.plus_minus is not None else None

        radar_players.append(
            RadarInput(
                player_id=nba_id,
                ppg=ppg,
                ts_pct=Decimal(str(adv.ts_pct or 0)) if adv else Decimal("0"),
                apg=apg,
                ast_pct=Decimal(str(adv.ast_pct or 0)) if adv else Decimal("0"),
                tov_per_game=tov_pg,
                stl_per_game=spg,
                blk_per_game=bpg,
                dfg_pct_diff=dfg_diff,
                deflections_per_game=defl_pg,
                efg_pct=Decimal(str(adv.efg_pct or 0)) if adv else Decimal("0"),
                usg_pct=Decimal(str(adv.usg_pct or 0)) if adv else Decimal("0"),
                fga_per_game=fga_pg,
                mpg=mpg,
                games_played=gp,
                clutch_pts=clutch_pts,
                clutch_plus_minus=clutch_pm,
                play_type_count=play_type_count,
            )
        )

    radar_calculator = RadarCalculator()
    radar_results = radar_calculator.calculate_all(radar_players)
    print(f"  - Calculated Radar for {len(radar_results)} players")

    # --- Step 8: Store all computed metrics ---
    print("\nStep 8: Storing computed metrics...")
    stored = 0

    # Collect all player IDs that have any computed result
    all_computed_ids = set()
    all_computed_ids.update(per_results.keys())
    all_computed_ids.update(bpm_results.keys())
    all_computed_ids.update(ws_results.keys())
    all_computed_ids.update(radar_results.keys())

    for nba_id in all_computed_ids:
        try:
            ss_player = season_stats_by_nba_id.get(nba_id)
            if not ss_player:
                continue
            _, player = ss_player

            # Upsert computed advanced record
            computed = (
                db.query(PlayerComputedAdvanced)
                .filter(
                    PlayerComputedAdvanced.player_id == player.id,
                    PlayerComputedAdvanced.season == season,
                )
                .first()
            )

            if not computed:
                computed = PlayerComputedAdvanced(
                    player_id=player.id,
                    season=season,
                )
                db.add(computed)

            # PER
            per_val = per_results.get(nba_id)
            if per_val is not None:
                computed.per = per_val

            # BPM
            bpm_val = bpm_results.get(nba_id)
            if bpm_val is not None:
                computed.obpm = bpm_val.obpm
                computed.dbpm = bpm_val.dbpm
                computed.bpm = bpm_val.bpm
                computed.vorp = bpm_val.vorp

            # Win Shares
            ws_val = ws_results.get(nba_id)
            if ws_val is not None:
                computed.ows = ws_val.ows
                computed.dws = ws_val.dws
                computed.ws = ws_val.ws
                computed.ws_per_48 = ws_val.ws_per_48

            # Radar
            radar_val = radar_results.get(nba_id)
            if radar_val is not None:
                computed.radar_scoring = radar_val.scoring
                computed.radar_playmaking = radar_val.playmaking
                computed.radar_defense = radar_val.defense
                computed.radar_efficiency = radar_val.efficiency
                computed.radar_volume = radar_val.volume
                computed.radar_durability = radar_val.durability
                computed.radar_clutch = radar_val.clutch
                computed.radar_versatility = radar_val.versatility

            stored += 1

            if verbose and stored % 50 == 0:
                print(f"  Stored {stored} players...")

        except Exception as e:
            logger.error("Error storing computed metrics for player %d: %s", nba_id, e)
            errors += 1

    try:
        db.commit()
        print(f"  - Stored computed metrics for {stored} players")
        logger.info("Stored computed metrics for %d players", stored)
    except Exception as e:
        logger.error("Failed to commit computed metrics: %s", e)
        db.rollback()
        return {"status": "error", "message": str(e)}

    return {
        "status": "success",
        "per_count": len(per_results),
        "bpm_count": len(bpm_results),
        "ws_count": len(ws_results),
        "radar_count": len(radar_results),
        "stored": stored,
        "errors": errors,
    }


def fetch_and_store_career_stats(
    db: Session,
    service: NBADataService,
    career_limit: int = 100,
    verbose: bool = False,
) -> dict:
    """Part C: Fetch career stats for top players and store in database.

    Fetches per-player career data from the NBA API for the top players
    by minutes played and stores each season row in PlayerCareerStats.

    Args:
        db: Database session
        service: NBADataService instance
        career_limit: Maximum number of players to fetch career stats for
        verbose: If True, print detailed progress

    Returns:
        Dict with status and counts
    """
    print(f"\n--- Part C: Fetching Career Stats (limit: {career_limit}) ---")
    errors = 0
    processed = 0

    # Find top players by total minutes
    top_players = (
        db.query(Player, SeasonStats)
        .join(SeasonStats, Player.id == SeasonStats.player_id)
        .filter(
            SeasonStats.total_minutes.isnot(None),
            SeasonStats.total_minutes > 0,
        )
        .order_by(desc(SeasonStats.total_minutes))
        .limit(career_limit)
        .all()
    )

    print(f"\nFetching career stats for {len(top_players)} players...")

    for idx, (player, _) in enumerate(top_players):
        try:
            if verbose:
                print(f"  [{idx + 1}/{len(top_players)}] Fetching career for {player.name}...")

            career_data = service.get_career_stats(player_id=player.nba_id)

            # Parse SeasonTotalsRegularSeason dataset
            season_totals = career_data.get("SeasonTotalsRegularSeason", [])
            if not season_totals:
                logger.debug("No career data for player %s (%d)", player.name, player.nba_id)
                continue

            for season_row in season_totals:
                season_id = season_row.get("SEASON_ID")
                if not season_id:
                    continue

                # Upsert career stats record
                existing = (
                    db.query(PlayerCareerStatsModel)
                    .filter(
                        PlayerCareerStatsModel.player_id == player.id,
                        PlayerCareerStatsModel.season == season_id,
                    )
                    .first()
                )

                if not existing:
                    existing = PlayerCareerStatsModel(
                        player_id=player.id,
                        season=season_id,
                    )
                    db.add(existing)

                existing.games_played = safe_int(season_row.get("GP"))
                existing.minutes = safe_decimal(season_row.get("MIN"))
                existing.ppg = safe_decimal(season_row.get("PTS"))
                existing.rpg = safe_decimal(season_row.get("REB"))
                existing.apg = safe_decimal(season_row.get("AST"))
                existing.spg = safe_decimal(season_row.get("STL"))
                existing.bpg = safe_decimal(season_row.get("BLK"))
                existing.fg_pct = safe_decimal(season_row.get("FG_PCT"))
                existing.fg3_pct = safe_decimal(season_row.get("FG3_PCT"))
                existing.ft_pct = safe_decimal(season_row.get("FT_PCT"))
                existing.team_abbreviation = season_row.get("TEAM_ABBREVIATION")

            processed += 1

            if processed % 10 == 0:
                print(f"  Processed {processed}/{len(top_players)} players...")
                # Intermediate commit to avoid large transactions
                db.flush()

            # Respect API rate limits for per-player calls
            if idx < len(top_players) - 1:
                time.sleep(0.6)

        except (CircuitBreakerError, RateLimitError) as e:
            logger.warning("Rate limited fetching career for %s: %s", player.name, e)
            print(f"  [WARNING] Rate limited for {player.name}, skipping remaining...")
            break
        except Exception as e:
            logger.error("Error fetching career for %s: %s", player.name, e)
            errors += 1

    try:
        db.commit()
        print(f"  - Stored career stats for {processed} players")
        logger.info("Stored career stats for %d players", processed)
    except Exception as e:
        logger.error("Failed to commit career stats: %s", e)
        db.rollback()
        return {"status": "error", "message": str(e)}

    return {"status": "success", "processed": processed, "errors": errors}


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
        description="Fetch Phase 2 data: shooting tracking, computed metrics, and career stats",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    python -m scripts.fetch_phase2_data --season 2024-25
    python -m scripts.fetch_phase2_data --season 2024-25 --create-tables
    python -m scripts.fetch_phase2_data --season 2024-25 --career-limit 50
    python -m scripts.fetch_phase2_data --season 2024-25 --verbose
    python -m scripts.fetch_phase2_data --season 2024-25 --no-cache
        """,
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
        "--career-limit",
        type=int,
        default=100,
        help="Max number of players to fetch career stats for (default: 100)",
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
        "--skip-career",
        action="store_true",
        help="Skip career stats fetch (Part C)",
    )
    args = parser.parse_args()

    setup_logging(args.verbose)

    print("\n" + "=" * 60)
    print("CORTEX Phase 2 Data Fetcher")
    print("=" * 60)

    print(f"\nConfiguration:")
    print(f"  Season: {args.season}")
    print(f"  Career limit: {args.career_limit}")
    print(f"  Cache bypass: {args.no_cache}")
    print(f"  Skip career: {args.skip_career}")
    print(f"\n  NOTE: This script makes ~7+ API calls (plus per-player career calls)")
    print(f"        Expected runtime: 2-5 minutes with rate limiting")

    if args.create_tables:
        create_tables()

    db = SessionLocal()
    try:
        service = NBADataService(bypass_cache=args.no_cache)

        # Part A: Fetch and store shooting tracking
        part_a_result = fetch_and_store_shooting_tracking(
            args.season, db, service, verbose=args.verbose
        )
        print(f"\n  Part A result: {part_a_result}")

        # Part B: Compute and store metrics
        part_b_result = compute_and_store_metrics(
            args.season, db, service, verbose=args.verbose
        )
        print(f"\n  Part B result: {part_b_result}")

        # Part C: Fetch career stats
        if not args.skip_career:
            part_c_result = fetch_and_store_career_stats(
                db, service,
                career_limit=args.career_limit,
                verbose=args.verbose,
            )
            print(f"\n  Part C result: {part_c_result}")

        print_circuit_breaker_status()
        print_cache_status()

        all_success = (
            part_a_result.get("status") == "success"
            and part_b_result.get("status") == "success"
        )

        if all_success:
            print("\n" + "=" * 60)
            print("Phase 2 data fetch completed successfully!")
            print("=" * 60 + "\n")
            return 0
        else:
            print("\n" + "=" * 60)
            print("[WARNING] Phase 2 data fetch completed with errors")
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
