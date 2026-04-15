#!/usr/bin/env python3
"""Seed all newly added stats for every available season.

Runs the 5 new/updated fetch phases:
1. Bio data + team records (2024-25 -> 2013-14)
2. Phase 1 re-run for paint/post/elbow touches (2024-25 -> 2013-14)
3. Play types re-run for handoff (2024-25 -> 2015-16)
4. Advanced tracking: speed/passing/rebounding/defender distance/def play types (2024-25 -> 2013-14)
5. Game logs + consistency (2024-25 -> 2013-14)

Usage:
    python -m scripts.seed_new_stats
    python -m scripts.seed_new_stats --only bio tracking_advanced game_logs
    python -m scripts.seed_new_stats --from-season 2020-21
    python -m scripts.seed_new_stats --dry-run
"""

import argparse
import subprocess
import sys
import time
from pathlib import Path

from scripts.shared import generate_seasons

ROOT = Path(__file__).parent.parent

PHASES = [
    {
        "key": "bio",
        "label": "Bio Data + Team Records",
        "module": "scripts.fetch_bio_data",
        "earliest": "2013-14",
    },
    {
        "key": "phase1_touches",
        "label": "Phase 1 Re-run (paint/post/elbow touches)",
        "module": "scripts.fetch_data",
        "earliest": "2013-14",
    },
    {
        "key": "play_types_handoff",
        "label": "Play Types Re-run (+ handoff)",
        "module": "scripts.fetch_play_type_data",
        "earliest": "2015-16",
    },
    {
        "key": "tracking_advanced",
        "label": "Advanced Tracking (speed/passing/reb/defender dist/def play types)",
        "module": "scripts.fetch_tracking_advanced",
        "earliest": "2013-14",
    },
    {
        "key": "game_logs",
        "label": "Game Logs + Consistency Metrics",
        "module": "scripts.fetch_game_logs",
        "earliest": "2013-14",
    },
]

ALL_KEYS = [p["key"] for p in PHASES]


def run_phase(module: str, season: str, label: str) -> bool:
    cmd = [sys.executable, "-m", module, "--season", season]
    print(f"\n  [{season}] {label}...")
    result = subprocess.run(cmd, cwd=ROOT, capture_output=True, text=True)
    if result.returncode != 0:
        output = (result.stdout + result.stderr).strip()
        last_lines = output.split("\n")[-3:]
        print(f"    [WARN] Failed (exit {result.returncode})")
        for line in last_lines:
            print(f"    {line}")
        return False
    print(f"    [OK]")
    return True


def main():
    parser = argparse.ArgumentParser(description="Seed all new stats for every season")
    parser.add_argument("--from-season", default="2013-14")
    parser.add_argument("--to-season", default="2024-25")
    parser.add_argument("--only", nargs="+", choices=ALL_KEYS)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    active = PHASES if not args.only else [p for p in PHASES if p["key"] in args.only]
    all_seasons = list(reversed(generate_seasons(args.from_season, args.to_season)))

    total_tasks = sum(
        1 for p in active for s in all_seasons if s >= p["earliest"]
    )

    print("\n" + "#" * 60)
    print("#  New Stats Seeder")
    print(f"#  Seasons: {all_seasons[-1]} -> {all_seasons[0]} ({len(all_seasons)} seasons)")
    print(f"#  Phases:  {len(active)}")
    print(f"#  Total tasks: {total_tasks}")
    print("#" * 60)

    if args.dry_run:
        print("\n  [DRY RUN] Plan:")
        for phase in active:
            applicable = [s for s in all_seasons if s >= phase["earliest"]]
            print(f"\n  {phase['label']}:")
            print(f"    Seasons: {applicable[-1]} -> {applicable[0]} ({len(applicable)})")
        return 0

    start = time.time()
    ok = 0
    fail = 0

    for phase in active:
        applicable = sorted(
            [s for s in all_seasons if s >= phase["earliest"]],
            reverse=True,
        )
        print(f"\n{'=' * 60}")
        print(f"  {phase['label']} ({len(applicable)} seasons)")
        print(f"{'=' * 60}")

        for season in applicable:
            success = run_phase(phase["module"], season, phase["label"])
            if success:
                ok += 1
            else:
                fail += 1

    elapsed = time.time() - start
    hours = int(elapsed // 3600)
    minutes = int((elapsed % 3600) // 60)
    seconds = int(elapsed % 60)

    print(f"\n{'#' * 60}")
    print(f"#  Done! {ok} succeeded, {fail} failed")
    print(f"#  Time: {hours}h {minutes}m {seconds}s")
    print(f"{'#' * 60}\n")

    return 1 if fail > 0 else 0


if __name__ == "__main__":
    sys.exit(main())
