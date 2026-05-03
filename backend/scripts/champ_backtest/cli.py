"""Command-line entry point for the Championship Index backtest harness.

Usage (from ``backend/``)::

    python -m scripts.champ_backtest.cli collect [--no-refresh]
    python -m scripts.champ_backtest.cli score   [--no-refresh]
    python -m scripts.champ_backtest.cli validate
    python -m scripts.champ_backtest.cli all
    python -m scripts.champ_backtest.cli demo

The ``demo`` subcommand generates a small synthetic dataset and runs the
full scoring + validation pipeline locally -- handy for plumbing checks
without hitting any networks.
"""

from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger("champ_backtest")


# ---------------------------------------------------------------------------
# Subcommand handlers
# ---------------------------------------------------------------------------


def cmd_collect(args: argparse.Namespace) -> int:
    """Pull historical title-winners and contender controls."""
    from scripts.champ_backtest import data_collection

    refresh = not args.no_refresh
    print(f"[collect] fetching title winners (refresh={refresh})", file=sys.stderr)
    winners = data_collection.fetch_title_winners(refresh=refresh)
    print(f"[collect] {len(winners)} title-winner rows", file=sys.stderr)

    print(f"[collect] fetching contender controls (refresh={refresh})", file=sys.stderr)
    controls = data_collection.fetch_contender_controls(refresh=refresh)
    print(f"[collect] {len(controls)} control rows", file=sys.stderr)
    return 0


def cmd_score(args: argparse.Namespace) -> int:
    """Score every cached row through the production calculator."""
    from scripts.champ_backtest import compute_index, data_collection

    controls = data_collection.fetch_contender_controls(refresh=False)
    if not controls:
        print(
            "[score] no controls cached -- run `collect` first",
            file=sys.stderr,
        )
        return 1
    print(f"[score] scoring {len(controls)} rows", file=sys.stderr)
    df = compute_index.score_dataset(controls)
    print(f"[score] produced {len(df)} scored rows", file=sys.stderr)
    return 0


def cmd_validate(args: argparse.Namespace) -> int:
    """Compute calibration / discrimination metrics + write summary.md."""
    from scripts.champ_backtest import compute_index, validate as validate_mod

    if not compute_index.SCORED_PATH.exists():
        print(
            f"[validate] no scored parquet at {compute_index.SCORED_PATH} -- run `score` first",
            file=sys.stderr,
        )
        return 1
    scored = pd.read_parquet(compute_index.SCORED_PATH)
    print(f"[validate] loaded {len(scored)} scored rows", file=sys.stderr)
    report = validate_mod.validate(scored)
    print(
        f"[validate] AUC={report.auc:.3f}, Brier={report.brier:.4f}, "
        f"k={report.fitted_k:.4f}, base={report.fitted_base:.4f}",
        file=sys.stderr,
    )
    print(f"[validate] wrote {validate_mod.SUMMARY_PATH}", file=sys.stderr)
    return 0


def cmd_all(args: argparse.Namespace) -> int:
    """Run collect -> score -> validate end-to-end."""
    rc = cmd_collect(args)
    if rc:
        return rc
    rc = cmd_score(args)
    if rc:
        return rc
    return cmd_validate(args)


def cmd_demo(args: argparse.Namespace) -> int:
    """Run scoring + validation on a tiny synthetic dataset (no network).

    This is the recommended smoke-test path during development -- it
    exercises every code path in :mod:`feature_extraction`,
    :mod:`compute_index`, and :mod:`validate` without touching the network
    or relying on cached data.
    """
    from scripts.champ_backtest import compute_index, validate as validate_mod

    print("[demo] building synthetic player-season rows", file=sys.stderr)
    rows = _synthetic_rows()
    scored = compute_index.score_dataset(rows, persist=False)
    print(f"[demo] scored {len(scored)} synthetic rows", file=sys.stderr)
    if scored.empty:
        print("[demo] scoring produced empty DataFrame -- aborting", file=sys.stderr)
        return 1
    out_dir = Path(args.demo_out) if args.demo_out else validate_mod.OUTPUT_DIR
    out_dir.mkdir(parents=True, exist_ok=True)
    # Redirect output paths for the demo run so we don't clobber the real
    # validation artefacts.
    summary_path = out_dir / "summary_demo.md"
    plot_path = out_dir / "calibration_demo.png"
    report = validate_mod.validate(scored, write_files=False)
    summary_path.write_text(report.summary_md)
    validate_mod._plot_calibration(
        report.decile_table, report.fitted_k, report.fitted_base, plot_path
    )
    print(f"[demo] wrote {summary_path}", file=sys.stderr)
    print(f"[demo] wrote {plot_path}", file=sys.stderr)
    print(
        f"[demo] AUC={report.auc:.3f} Brier={report.brier:.4f} "
        f"refit_k={report.fitted_k:.4f} refit_base={report.fitted_base:.4f}",
        file=sys.stderr,
    )
    return 0


# ---------------------------------------------------------------------------
# Synthetic data for the demo path
# ---------------------------------------------------------------------------


def _synthetic_rows() -> list[dict[str, Any]]:
    """Generate a tiny but realistic synthetic dataset.

    Two real-feeling player-seasons (champion #1 options) plus 30 control
    rows drawn from a noisy baseline. Just enough variation that the
    logistic regression fits and the decile calibration table is well-formed.
    """
    rng = np.random.default_rng(seed=42)

    rows: list[dict[str, Any]] = []
    # Two title-winning #1 options: high BPM, high TS, healthy minutes
    rows.append(
        {
            "season": "2015-16",
            "player_name": "Synthetic Champ A",
            "team": "AAA",
            "won_title": True,
            "bpm": 11.9,
            "obpm": 7.9,
            "dbpm": 4.0,
            "ts_pct": 0.66,
            "usg_pct": 0.32,
            "games": 79,
            "minutes": 2700,
            "total_points": 2375,
            "total_fga": 1597,
            "total_fta": 400,
            "total_assists": 527,
            "def_rating": 102.0,
        }
    )
    rows.append(
        {
            "season": "2017-18",
            "player_name": "Synthetic Champ B",
            "team": "BBB",
            "won_title": True,
            "bpm": 10.4,
            "obpm": 7.2,
            "dbpm": 3.2,
            "ts_pct": 0.62,
            "usg_pct": 0.31,
            "games": 78,
            "minutes": 2900,
            "total_points": 2200,
            "total_fga": 1500,
            "total_fta": 600,
            "total_assists": 700,
            "def_rating": 105.0,
        }
    )

    # 30 controls -- mostly non-winners, with deliberately weaker profiles.
    for i in range(30):
        bpm = float(rng.normal(loc=4.0, scale=2.0))
        rows.append(
            {
                "season": f"20{15 + i % 8:02d}-{16 + i % 8:02d}",
                "player_name": f"Synthetic Control {i:02d}",
                "team": f"T{i % 10}",
                "won_title": False,
                "bpm": bpm,
                "obpm": float(rng.normal(loc=2.5, scale=1.5)),
                "dbpm": float(rng.normal(loc=1.5, scale=1.0)),
                "ts_pct": float(rng.uniform(0.52, 0.61)),
                "usg_pct": float(rng.uniform(0.18, 0.28)),
                "games": int(rng.integers(60, 82)),
                "minutes": int(rng.integers(1800, 2700)),
                "total_points": int(rng.integers(1000, 2000)),
                "total_fga": int(rng.integers(900, 1500)),
                "total_fta": int(rng.integers(150, 400)),
                "total_assists": int(rng.integers(150, 600)),
                "def_rating": float(rng.uniform(105.0, 115.0)),
            }
        )
    return rows


# ---------------------------------------------------------------------------
# argparse plumbing
# ---------------------------------------------------------------------------


def build_parser() -> argparse.ArgumentParser:
    """Build the top-level argparse parser."""
    parser = argparse.ArgumentParser(
        prog="champ_backtest",
        description=(
            "Historical-validation harness for the Championship Index. "
            "Runs collect / score / validate stages independently or end-to-end."
        ),
    )
    parser.add_argument(
        "-v",
        "--verbose",
        action="store_true",
        help="Enable INFO-level logging on stderr.",
    )
    sub = parser.add_subparsers(dest="cmd", required=True, metavar="<cmd>")

    p_collect = sub.add_parser("collect", help="Scrape historical data into cache/")
    p_collect.add_argument(
        "--no-refresh",
        action="store_true",
        help="Reuse parquet caches if present (skips network).",
    )
    p_collect.set_defaults(func=cmd_collect)

    p_score = sub.add_parser("score", help="Score cached rows via ChampionshipCalculator")
    p_score.add_argument("--no-refresh", action="store_true")
    p_score.set_defaults(func=cmd_score)

    p_validate = sub.add_parser(
        "validate",
        help="Compute AUC / Brier / decile / weights / calibration; write output/summary.md",
    )
    p_validate.add_argument("--no-refresh", action="store_true")
    p_validate.set_defaults(func=cmd_validate)

    p_all = sub.add_parser("all", help="Run collect -> score -> validate")
    p_all.add_argument("--no-refresh", action="store_true")
    p_all.set_defaults(func=cmd_all)

    p_demo = sub.add_parser(
        "demo",
        help="Run scoring + validation on synthetic data (no network).",
    )
    p_demo.add_argument(
        "--demo-out",
        default=None,
        help="Override the output directory (defaults to scripts/champ_backtest/output).",
    )
    p_demo.add_argument("--no-refresh", action="store_true")
    p_demo.set_defaults(func=cmd_demo)

    return parser


def main(argv: list[str] | None = None) -> int:
    """argparse entry point."""
    parser = build_parser()
    args = parser.parse_args(argv)
    logging.basicConfig(
        level=logging.INFO if args.verbose else logging.WARNING,
        format="%(asctime)s %(levelname)s %(name)s :: %(message)s",
        stream=sys.stderr,
    )
    return int(args.func(args))


if __name__ == "__main__":  # pragma: no cover
    raise SystemExit(main())
