#!/usr/bin/env python3
"""Full startup script — seeds ALL data for EVERY available season.

Runs migrations, then seeds 2024-25 first (creates player records that
historical seasons reference), then backfills every season from 2023-24
down to 2013-14 with all applicable phases.

Usage:
    docker compose --profile seed-all run --rm seed-all

    # Or locally:
    python -m scripts.seed_everything
    python -m scripts.seed_everything --from-season 2020-21
    python -m scripts.seed_everything --only phase1 phase2
    python -m scripts.seed_everything --dry-run
    python -m scripts.seed_everything --skip-current
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

from scripts.shared import generate_seasons

ROOT = Path(__file__).parent.parent  # backend/

CURRENT_SEASON = "2024-25"

# All phases with their earliest available season
PHASES = [
    {
        "key": "phase1",
        "label": "Phase 1: Traditional + Tracking Stats",
        "module": "scripts.fetch_data",
        "earliest": "2013-14",
    },
    {
        "key": "bio",
        "label": "Phase 1b: Player Bio & Team Records",
        "module": "scripts.fetch_bio_data",
        "earliest": "2013-14",
    },
    {
        "key": "phase2",
        "label": "Phase 2: Computed Advanced (PER, BPM, WS)",
        "module": "scripts.fetch_phase2_data",
        "earliest": "2013-14",
    },
    {
        "key": "advanced",
        "label": "Phase 3: Advanced Stats + Shot Zones + Clutch + Defense",
        "module": "scripts.fetch_advanced_data",
        "earliest": "2013-14",
    },
    {
        "key": "tracking_advanced",
        "label": "Phase 3b: Speed/Passing/Rebounding/Defender Distance/Def Play Types",
        "module": "scripts.fetch_tracking_advanced",
        "earliest": "2013-14",
    },
    {
        "key": "touches_opp_defense",
        "label": "Phase 3c: Elbow/Post/Paint Touches + Opponent Shooting Defense",
        "module": "scripts.fetch_touches_and_opp_defense",
        "earliest": "2013-14",
    },
    {
        "key": "play_types",
        "label": "Phase 4: Play Type Stats",
        "module": "scripts.fetch_play_type_data",
        "earliest": "2015-16",
    },
    {
        "key": "impact",
        "label": "Phase 5: Impact + On/Off + Lineups",
        "module": "scripts.fetch_impact_data",
        "earliest": "2013-14",
    },
    {
        "key": "matchups",
        "label": "Phase 6: Player Matchups",
        "module": "scripts.fetch_matchup_data",
        "earliest": "2016-17",
    },
    {
        "key": "all_in_one",
        "label": "Phase 7: All-In-One Metrics (EPM, DARKO, LEBRON, RPM)",
        "module": "scripts.fetch_all_in_one_data",
        "earliest": "2024-25",  # External scraped data — mostly paywalled for historical
    },
    {
        "key": "game_logs",
        "label": "Phase 7b: Game Logs & Consistency Metrics",
        "module": "scripts.fetch_game_logs",
        "earliest": "2013-14",
    },
    {
        "key": "nbarapm",
        "label": "Phase 8: nbarapm.com (RAPM, Big Board, RAPTOR, MAMBA)",
        "module": "scripts.fetch_nbarapm_data",
        "earliest": "2024-25",  # nbarapm.com — season-independent, run once
    },
]

ALL_PHASE_KEYS = [p["key"] for p in PHASES]



def run(label: str, cmd: list[str], allow_fail: bool = False) -> bool:
    """Run a subprocess with a visible label."""
    print(f"\n  {label}...")
    result = subprocess.run(cmd, cwd=ROOT)
    if result.returncode != 0:
        if allow_fail:
            print(f"    [WARN] {label} exited with code {result.returncode} (continuing)")
            return False
        else:
            print(f"\n  [ERROR] {label} failed with exit code {result.returncode}")
            sys.exit(result.returncode)
    return True


def run_phase_for_season(phase: dict, season: str) -> bool:
    """Run a single phase for a single season."""
    cmd = [sys.executable, "-m", phase["module"], "--season", season]
    label = f"[{season}] {phase['label']}"
    print(f"\n  {label}...")
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        output = (result.stdout + result.stderr).strip()
        last_lines = output.split("\n")[-5:]
        print(f"    [WARN] Failed (exit {result.returncode})")
        for line in last_lines:
            print(f"    {line}")
        return False
    print(f"    [OK]")
    return True


def main():
    parser = argparse.ArgumentParser(description="Seed ALL NBA stats data for every season")
    parser.add_argument(
        "--from-season", default="2013-14",
        help="Earliest historical season (default: 2013-14)",
    )
    parser.add_argument(
        "--to-season", default="2023-24",
        help="Latest historical season (default: 2023-24)",
    )
    parser.add_argument(
        "--current-season", default=CURRENT_SEASON,
        help=f"Current season to seed first (default: {CURRENT_SEASON})",
    )
    parser.add_argument(
        "--skip-current", action="store_true",
        help="Skip the current season (only run historical)",
    )
    parser.add_argument(
        "--skip-migrations", action="store_true",
        help="Skip Alembic migrations",
    )
    parser.add_argument(
        "--only", nargs="+", choices=ALL_PHASE_KEYS,
        help="Run only specific phases",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    args = parser.parse_args()

    active_phases = PHASES
    if args.only:
        active_phases = [p for p in PHASES if p["key"] in args.only]

    historical_seasons = generate_seasons(args.from_season, args.to_season)
    current = args.current_season

    # Build the full season list: current first, then historical newest-to-oldest
    all_seasons = []
    if not args.skip_current:
        all_seasons.append(current)
    all_seasons.extend(reversed(historical_seasons))

    total_tasks = 0
    for phase in active_phases:
        for season in all_seasons:
            if season >= phase["earliest"]:
                total_tasks += 1

    print("\n" + "#" * 60)
    print("#  StatFloor Full Data Seeder")
    print(f"#  Seasons: {all_seasons[-1]} -> {all_seasons[0]} ({len(all_seasons)} seasons)")
    print(f"#  Phases:  {len(active_phases)}")
    print(f"#  Total fetch tasks: {total_tasks}")
    print("#" * 60)

    if args.dry_run:
        print("\n  [DRY RUN] Execution plan:\n")
        if not args.skip_migrations:
            print("  0. Run Alembic migrations")
        if not args.skip_current:
            print(f"\n  --- Current season ({current}) ---")
            for phase in active_phases:
                if current >= phase["earliest"]:
                    print(f"    {phase['label']}")
        print(f"\n  --- Historical ({args.from_season} -> {args.to_season}) ---")
        for phase in active_phases:
            applicable = [s for s in historical_seasons if s >= phase["earliest"]]
            if applicable:
                print(f"  {phase['label']}:")
                print(f"    {applicable[0]} -> {applicable[-1]} ({len(applicable)} seasons)")
        return 0

    start = time.time()
    total_ok = 0
    total_fail = 0

    # Step 0: Migrations
    if not args.skip_migrations:
        print(f"\n{'=' * 60}")
        print("  Running Alembic migrations")
        print(f"{'=' * 60}")
        run("Alembic migrations", ["alembic", "upgrade", "head"])

    # Step 1: Seed current season first (all phases)
    # This creates player records needed by historical seasons
    if not args.skip_current:
        print(f"\n{'=' * 60}")
        print(f"  Current season: {current} (all phases)")
        print(f"{'=' * 60}")
        for phase in active_phases:
            if current >= phase["earliest"]:
                ok = run_phase_for_season(phase, current)
                total_ok += 1 if ok else 0
                total_fail += 0 if ok else 1

    # Step 2: Historical seasons — run each phase across all its applicable seasons
    # Phase-first ordering is more efficient (keeps API endpoint patterns consistent)
    print(f"\n{'=' * 60}")
    print(f"  Historical seasons: {args.from_season} -> {args.to_season}")
    print(f"{'=' * 60}")

    for phase in active_phases:
        # Skip phases that only apply to current season
        if phase["earliest"] == current:
            continue

        applicable = sorted(
            [s for s in historical_seasons if s >= phase["earliest"]],
            reverse=True,  # newest first
        )
        if not applicable:
            continue

        print(f"\n  --- {phase['label']} ({len(applicable)} seasons) ---")
        phase_ok = 0
        phase_fail = 0
        for season in applicable:
            ok = run_phase_for_season(phase, season)
            if ok:
                phase_ok += 1
            else:
                phase_fail += 1

        total_ok += phase_ok
        total_fail += phase_fail
        print(f"\n  {phase['label']}: {phase_ok}/{len(applicable)} succeeded")

    elapsed = time.time() - start
    hours = int(elapsed // 3600)
    minutes = int((elapsed % 3600) // 60)
    seconds = int(elapsed % 60)

    print(f"\n{'#' * 60}")
    print(f"#  Full seed complete!")
    print(f"#  Results: {total_ok} succeeded, {total_fail} failed")
    print(f"#  Total time: {hours}h {minutes}m {seconds}s")
    print(f"{'#' * 60}\n")

    return 1 if total_fail > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
