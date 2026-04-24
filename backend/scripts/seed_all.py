#!/usr/bin/env python3
"""Master seed script — runs migrations and all data fetch scripts in order.

DEPRECATED: Use ``seed_everything.py`` instead, which covers all 13 phases
(this script only covers 8) and supports multi-season seeding::

    python -m scripts.seed_everything                          # current + historical
    python -m scripts.seed_everything --from-season 2024-25    # current season only
    python -m scripts.seed_everything --only phase1 phase2

Docker: ``docker compose --profile seed-all run --rm seed-all``

This script is kept for backward compatibility but will be removed in a
future release.
"""

import argparse
import subprocess
import sys
import time
import warnings
from pathlib import Path

ROOT = Path(__file__).parent.parent  # backend/


def run(label: str, cmd: list[str], allow_fail: bool = False) -> bool:
    """Run a subprocess with a visible label."""
    print(f"\n{'='*60}")
    print(f"  {label}")
    print(f"{'='*60}\n")

    result = subprocess.run(cmd, cwd=ROOT)

    if result.returncode != 0:
        if allow_fail:
            print(f"\n  [WARN] {label} exited with code {result.returncode} (continuing)")
            return False
        else:
            print(f"\n  [ERROR] {label} failed with exit code {result.returncode}")
            sys.exit(result.returncode)
    return True


def main():
    warnings.warn(
        "seed_all.py is deprecated. "
        "Use 'python -m scripts.seed_everything' instead "
        "(supports all 13 phases vs 8 here, plus multi-season seeding).",
        DeprecationWarning,
        stacklevel=2,
    )
    parser = argparse.ArgumentParser(description="Seed all NBA stats data")
    parser.add_argument("--season", default="2025-26", help="NBA season (default: 2025-26)")
    parser.add_argument("--skip-migrations", action="store_true", help="Skip Alembic migrations")
    parser.add_argument(
        "--only",
        nargs="+",
        choices=["phase1", "phase2", "advanced", "play_types", "impact", "matchups", "all_in_one", "nbarapm"],
        help="Run only specific fetch phases",
    )
    args = parser.parse_args()

    season = args.season
    phases = args.only

    start = time.time()
    print("\n" + "#" * 60)
    print("#  StatFloor Data Seeder")
    print(f"#  Season: {season}")
    print("#" * 60)

    # Step 0: Migrations
    if not args.skip_migrations:
        run("Running Alembic migrations", ["alembic", "upgrade", "head"])

    # Define all phases in order
    all_phases = [
        ("phase1", "Phase 1: Traditional + Tracking Stats", [
            sys.executable, "-m", "scripts.fetch_data", "--season", season,
        ]),
        ("phase2", "Phase 2: Computed Advanced (PER, BPM, WS)", [
            sys.executable, "-m", "scripts.fetch_phase2_data", "--season", season,
        ]),
        ("advanced", "Phase 3: Advanced Stats + Shot Zones + Clutch + Defense", [
            sys.executable, "-m", "scripts.fetch_advanced_data", "--season", season,
        ]),
        ("play_types", "Phase 4: Play Type Stats", [
            sys.executable, "-m", "scripts.fetch_play_type_data", "--season", season,
        ]),
        ("impact", "Phase 5: Impact + On/Off + Lineups", [
            sys.executable, "-m", "scripts.fetch_impact_data", "--season", season,
        ]),
        ("matchups", "Phase 6: Player Matchups", [
            sys.executable, "-m", "scripts.fetch_matchup_data", "--season", season,
        ]),
        ("all_in_one", "Phase 7: All-In-One Metrics (EPM, DARKO, LEBRON, RPM)", [
            sys.executable, "-m", "scripts.fetch_all_in_one_data", "--season", season,
        ]),
        ("nbarapm", "Phase 8: nbarapm.com (RAPM Windows, Big Board, Six Factor, Peak, RAPTOR, MAMBA, rFTOV)", [
            sys.executable, "-m", "scripts.fetch_nbarapm_data", "--season", season,
        ]),
    ]

    # Filter phases if --only specified
    if phases:
        all_phases = [(key, label, cmd) for key, label, cmd in all_phases if key in phases]

    # Run each phase
    succeeded = 0
    failed = 0
    for key, label, cmd in all_phases:
        ok = run(label, cmd, allow_fail=True)
        if ok:
            succeeded += 1
        else:
            failed += 1

    elapsed = time.time() - start
    minutes = int(elapsed // 60)
    seconds = int(elapsed % 60)

    print("\n" + "#" * 60)
    print(f"#  Seeding complete: {succeeded} succeeded, {failed} failed")
    print(f"#  Total time: {minutes}m {seconds}s")
    print("#" * 60 + "\n")

    sys.exit(1 if failed > 0 else 0)


if __name__ == "__main__":
    main()
