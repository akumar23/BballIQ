#!/usr/bin/env python3
"""Fetch historical NBA data for multiple past seasons.

Orchestrates all fetch scripts across seasons 2013-14 through 2023-24.
Must be run after the current season (2024-25) is already seeded since
it creates player records that past seasons reference.

Usage:
    python -m scripts.fetch_historical
    python -m scripts.fetch_historical --from-season 2020-21
    python -m scripts.fetch_historical --only phase1 phase2 advanced
    python -m scripts.fetch_historical --dry-run
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

ROOT = Path(__file__).parent.parent

# NBA API data availability by script
PHASES = [
    {
        "key": "phase1",
        "label": "Traditional + Tracking Stats",
        "cmd": [sys.executable, "-m", "scripts.fetch_data"],
        "earliest": "2013-14",
    },
    {
        "key": "phase2",
        "label": "Computed Advanced (PER, BPM, WS)",
        "cmd": [sys.executable, "-m", "scripts.fetch_phase2_data"],
        "earliest": "2013-14",
    },
    {
        "key": "advanced",
        "label": "Advanced Stats + Shot Zones + Clutch + Defense",
        "cmd": [sys.executable, "-m", "scripts.fetch_advanced_data"],
        "earliest": "2013-14",
    },
    {
        "key": "play_types",
        "label": "Play Type Stats",
        "cmd": [sys.executable, "-m", "scripts.fetch_play_type_data"],
        "earliest": "2015-16",
    },
    {
        "key": "impact",
        "label": "Impact + On/Off + Lineups",
        "cmd": [sys.executable, "-m", "scripts.fetch_impact_data"],
        "earliest": "2013-14",
    },
    {
        "key": "matchups",
        "label": "Player Matchups",
        "cmd": [sys.executable, "-m", "scripts.fetch_matchup_data"],
        "earliest": "2016-17",
    },
]

DEFAULT_END = "2023-24"


def generate_seasons(from_season: str, to_season: str) -> list[str]:
    """Generate list of NBA season strings."""
    start = int(from_season.split("-")[0])
    end = int(to_season.split("-")[0])
    seasons = []
    for year in range(start, end + 1):
        short = str(year + 1)[-2:]
        seasons.append(f"{year}-{short}")
    return seasons


def run_phase(label: str, cmd: list[str], season: str) -> bool:
    """Run a single phase for a single season."""
    full_cmd = cmd + ["--season", season]
    print(f"\n  [{season}] {label}...")
    result = subprocess.run(full_cmd, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        # Print last few lines of stderr/stdout on failure
        output = result.stdout + result.stderr
        last_lines = output.strip().split("\n")[-5:]
        print(f"    [WARN] Failed (exit {result.returncode})")
        for line in last_lines:
            print(f"    {line}")
        return False
    return True


def main():
    parser = argparse.ArgumentParser(description="Fetch historical NBA data")
    parser.add_argument(
        "--from-season", default="2013-14",
        help="Start season (default: 2013-14, when tracking data began)",
    )
    parser.add_argument(
        "--to-season", default=DEFAULT_END,
        help=f"End season (default: {DEFAULT_END})",
    )
    parser.add_argument(
        "--only", nargs="+",
        choices=[p["key"] for p in PHASES],
        help="Run only specific phases",
    )
    parser.add_argument("--dry-run", action="store_true", help="Print plan without executing")
    args = parser.parse_args()

    active_phases = PHASES
    if args.only:
        active_phases = [p for p in PHASES if p["key"] in args.only]

    all_seasons = generate_seasons(args.from_season, args.to_season)

    print("\n" + "#" * 60)
    print("#  StatFloor Historical Data Fetcher")
    print(f"#  Seasons: {args.from_season} → {args.to_season} ({len(all_seasons)} seasons)")
    print(f"#  Phases: {', '.join(p['key'] for p in active_phases)}")
    print("#" * 60)

    if args.dry_run:
        print("\n  [DRY RUN] Would execute:\n")
        for phase in active_phases:
            applicable = [s for s in all_seasons if s >= phase["earliest"]]
            print(f"  {phase['label']}:")
            print(f"    Seasons: {applicable[0]} → {applicable[-1]} ({len(applicable)} seasons)")
            print(f"    Earliest available: {phase['earliest']}")
        return 0

    start = time.time()
    total_ok = 0
    total_fail = 0

    # Run phase1 first for ALL seasons to ensure players exist,
    # then run remaining phases
    for phase in active_phases:
        applicable = [s for s in all_seasons if s >= phase["earliest"]]
        if not applicable:
            continue

        print(f"\n{'=' * 60}")
        print(f"  {phase['label']}")
        print(f"  Seasons: {applicable[0]} → {applicable[-1]} ({len(applicable)})")
        print(f"{'=' * 60}")

        phase_ok = 0
        phase_fail = 0
        for season in applicable:
            ok = run_phase(phase["label"], phase["cmd"], season)
            if ok:
                phase_ok += 1
            else:
                phase_fail += 1

        total_ok += phase_ok
        total_fail += phase_fail
        print(f"\n  {phase['label']}: {phase_ok} succeeded, {phase_fail} failed")

    elapsed = time.time() - start
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print(f"\n{'#' * 60}")
    print(f"#  Historical fetch complete: {total_ok} succeeded, {total_fail} failed")
    print(f"#  Total time: {minutes}m {seconds}s")
    print(f"{'#' * 60}\n")

    return 1 if total_fail > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
