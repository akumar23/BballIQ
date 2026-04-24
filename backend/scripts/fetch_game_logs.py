#!/usr/bin/env python3
"""Script to fetch game logs and compute consistency metrics.

Populates:
- GameStats (per-game box scores for every player)
- PlayerConsistencyStats (variance/volatility metrics computed from game logs)

Usage:
    python -m scripts.fetch_game_logs --season 2024-25
    python -m scripts.fetch_game_logs --season 2024-25 --verbose
"""

import argparse
import logging
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from sqlalchemy.orm import Session

from app.db.session import SessionLocal
from app.models import Player
from app.models.game_stats import GameStats
from app.models.consistency_stats import PlayerConsistencyStats
from app.services.nba_data import NBADataService
from app.services.rate_limiter import (
    CircuitBreakerError,
    RateLimitError,
    nba_api_circuit_breaker,
)
from scripts.shared import safe_decimal as _d, safe_int as _i, setup_logging

logger = logging.getLogger(__name__)

# Minimum games for consistency calculation
MIN_GAMES = 15


def game_score(row: dict) -> float:
    """Hollinger Game Score formula.

    GmSc = PTS + 0.4*FGM - 0.7*FGA - 0.4*(FTA-FTM) + 0.7*OREB + 0.3*DREB
           + STL + 0.7*AST + 0.7*BLK - 0.4*PF - TOV
    """
    pts = row.get("PTS") or 0
    fgm = row.get("FGM") or 0
    fga = row.get("FGA") or 0
    ftm = row.get("FTM") or 0
    fta = row.get("FTA") or 0
    oreb = row.get("OREB") or 0
    dreb = row.get("DREB") or 0
    stl = row.get("STL") or 0
    ast = row.get("AST") or 0
    blk = row.get("BLK") or 0
    pf = row.get("PF") or 0
    tov = row.get("TOV") or 0

    return (
        pts + 0.4 * fgm - 0.7 * fga - 0.4 * (fta - ftm)
        + 0.7 * oreb + 0.3 * dreb + stl + 0.7 * ast + 0.7 * blk
        - 0.4 * pf - tov
    )


def cv(values: list[float]) -> float | None:
    """Coefficient of variation (std / mean). Returns None if mean is 0."""
    if len(values) < 2:
        return None
    mean = statistics.mean(values)
    if mean == 0:
        return None
    return statistics.stdev(values) / abs(mean)


def fetch_and_store_game_logs(
    season: str,
    db: Session,
    verbose: bool = False,
    bypass_cache: bool = False,
) -> bool:
    """Fetch game logs, store in GameStats, compute consistency."""
    logger.info("Starting game log fetch for season %s", season)
    print(f"\nFetching game logs for season {season}...")
    print("-" * 50)

    service = NBADataService(bypass_cache=bypass_cache)

    # Build nba_id -> player.id lookup
    lookup = {p.nba_id: p.id for p in db.query(Player.nba_id, Player.id).all()}
    print(f"  Player lookup: {len(lookup)} players")

    # Step 1: Fetch game logs (single bulk API call)
    print("\nStep 1: Fetching game logs (single API call, ~30K rows)...")
    try:
        game_logs = service.get_player_game_logs(season)
        print(f"  Got {len(game_logs)} game log entries")
    except (CircuitBreakerError, RateLimitError) as e:
        print(f"  [ERROR] {e}")
        return False

    # Step 2: Clear existing game stats for this season and bulk insert
    print("\nStep 2: Storing game logs...")
    existing_game_ids = set(
        r[0] for r in db.query(GameStats.game_id)
        .filter(GameStats.season == season)
        .distinct()
        .all()
    )

    # Group by player for consistency calc
    player_games: dict[int, list[dict]] = {}  # player db id -> list of game rows

    new_records = 0
    skipped = 0
    for row in game_logs:
        nba_id = row.get("PLAYER_ID")
        pid = lookup.get(nba_id)
        if not pid:
            continue

        g_id = str(row.get("GAME_ID", ""))
        g_date = row.get("GAME_DATE", "")

        # Track for consistency
        if pid not in player_games:
            player_games[pid] = []
        player_games[pid].append(row)

        # Check if this specific game+player already exists
        exists = (
            db.query(GameStats.id)
            .filter(GameStats.player_id == pid, GameStats.game_id == g_id)
            .first()
        )
        if exists:
            skipped += 1
            continue

        gs = game_score(row)
        minutes_raw = row.get("MIN")
        minutes = _d(minutes_raw) if minutes_raw is not None else None

        rec = GameStats(
            player_id=pid,
            season=season,
            game_id=g_id,
            game_date=g_date[:10] if g_date else None,
            matchup=row.get("MATCHUP"),
            wl=row.get("WL"),
            minutes=minutes,
            points=_i(row.get("PTS")),
            assists=_i(row.get("AST")),
            rebounds=_i(row.get("REB")),
            offensive_rebounds=_i(row.get("OREB")),
            defensive_rebounds=_i(row.get("DREB")),
            steals=_i(row.get("STL")),
            blocks=_i(row.get("BLK")),
            blocks_against=_i(row.get("BLKA")),
            turnovers=_i(row.get("TOV")),
            personal_fouls=_i(row.get("PF")),
            fouls_drawn=_i(row.get("PFD")),
            plus_minus=_i(row.get("PLUS_MINUS")),
            fgm=_i(row.get("FGM")),
            fga=_i(row.get("FGA")),
            fg_pct=_d(row.get("FG_PCT")),
            fg3m=_i(row.get("FG3M")),
            fg3a=_i(row.get("FG3A")),
            fg3_pct=_d(row.get("FG3_PCT")),
            ftm=_i(row.get("FTM")),
            fta=_i(row.get("FTA")),
            ft_pct=_d(row.get("FT_PCT")),
            double_double=_i(row.get("DD2")),
            triple_double=_i(row.get("TD3")),
            fantasy_pts=_d(row.get("NBA_FANTASY_PTS")),
            game_score=_d(gs),
        )
        db.add(rec)
        new_records += 1

    print(f"  Inserted {new_records} new game records, skipped {skipped} existing")

    # Flush to ensure game stats are written
    db.flush()

    # Step 3: Compute consistency metrics
    print("\nStep 3: Computing consistency metrics...")
    consistency_count = 0

    for pid, games in player_games.items():
        if len(games) < MIN_GAMES:
            continue

        pts_list = [float(g.get("PTS") or 0) for g in games]
        ast_list = [float(g.get("AST") or 0) for g in games]
        reb_list = [float(g.get("REB") or 0) for g in games]
        fant_list = [float(g.get("NBA_FANTASY_PTS") or 0) for g in games]
        gs_list = [game_score(g) for g in games]

        # Boom/bust (scoring)
        pts_mean = statistics.mean(pts_list)
        pts_sd = statistics.stdev(pts_list) if len(pts_list) > 1 else 0
        boom_threshold = pts_mean + pts_sd
        bust_threshold = pts_mean - pts_sd
        boom = sum(1 for p in pts_list if p > boom_threshold)
        bust = sum(1 for p in pts_list if p < bust_threshold)
        n_games = len(games)

        # Streaks (above/below mean game score)
        gs_mean = statistics.mean(gs_list)
        above_streak = 0
        below_streak = 0
        best_streak = 0
        worst_streak = 0
        for gs_val in gs_list:
            if gs_val >= gs_mean:
                above_streak += 1
                below_streak = 0
                best_streak = max(best_streak, above_streak)
            else:
                below_streak += 1
                above_streak = 0
                worst_streak = max(worst_streak, below_streak)

        # DD/TD rates
        dd_count = sum(1 for g in games if (g.get("DD2") or 0) > 0)
        td_count = sum(1 for g in games if (g.get("TD3") or 0) > 0)

        rec = (
            db.query(PlayerConsistencyStats)
            .filter(PlayerConsistencyStats.player_id == pid, PlayerConsistencyStats.season == season)
            .first()
        )
        if not rec:
            rec = PlayerConsistencyStats(player_id=pid, season=season)
            db.add(rec)

        rec.games_used = n_games
        rec.pts_cv = _d(cv(pts_list))
        rec.ast_cv = _d(cv(ast_list))
        rec.reb_cv = _d(cv(reb_list))
        rec.fantasy_cv = _d(cv(fant_list))
        rec.game_score_cv = _d(cv(gs_list))
        rec.pts_std = _d(pts_sd)
        rec.ast_std = _d(statistics.stdev(ast_list)) if len(ast_list) > 1 else None
        rec.reb_std = _d(statistics.stdev(reb_list)) if len(reb_list) > 1 else None
        rec.game_score_std = _d(statistics.stdev(gs_list)) if len(gs_list) > 1 else None
        rec.game_score_avg = _d(gs_mean)
        rec.game_score_median = _d(statistics.median(gs_list))
        rec.game_score_max = _d(max(gs_list))
        rec.game_score_min = _d(min(gs_list))
        rec.boom_games = boom
        rec.bust_games = bust
        rec.boom_pct = _d(boom / n_games)
        rec.bust_pct = _d(bust / n_games)
        rec.best_streak = best_streak
        rec.worst_streak = worst_streak
        rec.dd_rate = _d(dd_count / n_games)
        rec.td_rate = _d(td_count / n_games)
        consistency_count += 1

    # Step 4: Calculate consistency percentiles (lower CV = higher percentile)
    print("  Calculating consistency percentiles...")
    all_consistency = (
        db.query(PlayerConsistencyStats)
        .filter(PlayerConsistencyStats.season == season)
        .all()
    )

    if all_consistency:
        # Sort by game_score_cv ascending (lower = more consistent = higher percentile)
        sorted_by_cv = sorted(
            [c for c in all_consistency if c.game_score_cv is not None],
            key=lambda c: float(c.game_score_cv),
            reverse=True,  # Highest CV first = lowest percentile
        )
        for i, c in enumerate(sorted_by_cv):
            c.consistency_score = int((i / len(sorted_by_cv)) * 100)

    # Commit
    try:
        db.commit()
        print(f"\nData committed:")
        print(f"  - {new_records} game logs inserted")
        print(f"  - {consistency_count} consistency profiles computed")
        print(f"  - {len(all_consistency)} consistency percentiles assigned")
        return True
    except Exception as e:
        logger.error("Failed to commit: %s", e)
        db.rollback()
        return False


def main() -> int:
    parser = argparse.ArgumentParser(description="Fetch game logs and compute consistency")
    parser.add_argument("--season", default="2025-26")
    parser.add_argument("--verbose", "-v", action="store_true")
    parser.add_argument("--no-cache", action="store_true")
    args = parser.parse_args()

    setup_logging(args.verbose)

    print("\n" + "=" * 60)
    print("NBA Game Logs & Consistency Metrics Fetcher")
    print("=" * 60)
    print(f"  Season: {args.season}")
    print(f"  Min games for consistency: {MIN_GAMES}")

    db = SessionLocal()
    try:
        success = fetch_and_store_game_logs(
            args.season, db, verbose=args.verbose, bypass_cache=args.no_cache
        )

        state = nba_api_circuit_breaker.state
        print(f"\nCircuit Breaker Status: {state.value}")

        if success:
            print("\n" + "=" * 60)
            print("Game logs fetch completed!")
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
