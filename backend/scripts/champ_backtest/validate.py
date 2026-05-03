"""Statistical validation of the Championship Index.

Given a scored DataFrame (output of :func:`compute_index.score_dataset`)
this module produces:

1. **AUC** of ``championship_index`` vs ``won_title``.
2. **Brier score** of ``win_probability`` vs ``won_title``.
3. **Decile calibration** -- mean predicted vs actual win rate per decile.
4. **Tier confusion** -- same as deciles but using the existing tier
   thresholds (90/80/70/60/45).
5. **Per-pillar differential** -- mean pillar for winners vs non-winners
   and Cohen's d effect size.
6. **Refit weights** -- logistic regression of ``won_title`` on the pillar
   scores, with standardised coefficients normalised to sum to 1.0.
7. **Recalibrated win-prob mapping** -- non-linear least-squares fit of
   ``actual_win_rate ~ base * exp(k * (index - 50))`` against the decile
   data.

Outputs a Markdown summary at ``output/summary.md`` and a calibration
plot at ``output/calibration.png``.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

logger = logging.getLogger(__name__)

OUTPUT_DIR = Path(__file__).resolve().parent / "output"
SUMMARY_PATH = OUTPUT_DIR / "summary.md"
CALIBRATION_PATH = OUTPUT_DIR / "calibration.png"

# Current production weights and tier thresholds (mirrored from
# app.services.championship). Kept as constants here so we can compare
# against the empirical refit; the parallel agent's branch may change
# these and the side-by-side table will show the delta.
CURRENT_WEIGHTS_7: dict[str, float] = {
    "playoff_scoring": 0.25,
    "two_way_impact": 0.20,
    "clutch_performance": 0.15,
    "portability": 0.15,
    "durability": 0.10,
    "experience_arc": 0.10,
    "supporting_cast": 0.05,
}
CURRENT_WEIGHTS_6: dict[str, float] = {
    "playoff_scoring": 0.27,
    "two_way_impact": 0.23,
    "clutch_performance": 0.15,
    "portability": 0.15,
    "durability": 0.10,
    "experience_arc": 0.10,
}
TIER_THRESHOLDS = [
    (90, "CHAMPIONSHIP ALPHA"),
    (80, "FUTURE ALPHA"),
    (70, "FLAWED ALPHA"),
    (60, "EMERGING ALPHA"),
    (45, "CHAMPIONSHIP PIECE"),
    (0, "RAW PROSPECT"),
]
HISTORICAL_BASE_RATE = 0.033
CURRENT_K = 0.03


# ---------------------------------------------------------------------------
# Result containers
# ---------------------------------------------------------------------------


@dataclass
class ValidationReport:
    """Aggregate of all statistics + the markdown summary it produced."""

    auc: float
    brier: float
    decile_table: pd.DataFrame
    tier_table: pd.DataFrame
    pillar_diff_table: pd.DataFrame
    fitted_weights: dict[str, float]
    weight_comparison: pd.DataFrame
    fitted_k: float
    fitted_base: float
    n_rows: int
    n_winners: int
    summary_md: str


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def validate(
    scored: pd.DataFrame,
    *,
    pillar_columns: list[str] | None = None,
    write_files: bool = True,
) -> ValidationReport:
    """Run the full validation pipeline.

    Args:
        scored: Output of :func:`compute_index.score_dataset`. Must contain
            ``championship_index``, ``win_probability``, ``won_title``, and
            one column per pillar.
        pillar_columns: Override list of pillar column names. If ``None``,
            auto-detected by excluding the fixed composite columns.
        write_files: When True, write ``summary.md`` and ``calibration.png``.

    Returns:
        :class:`ValidationReport` with all the computed tables.
    """
    if scored.empty:
        raise ValueError("scored DataFrame is empty -- nothing to validate")
    required = {"championship_index", "win_probability", "won_title"}
    missing = required - set(scored.columns)
    if missing:
        raise ValueError(f"scored DataFrame missing columns: {sorted(missing)}")

    if pillar_columns is None:
        pillar_columns = _detect_pillar_columns(scored)

    auc = _compute_auc(scored)
    brier = _compute_brier(scored)
    decile_table = _decile_calibration(scored)
    tier_table = _tier_calibration(scored)
    pillar_diff_table = _pillar_differential(scored, pillar_columns)
    fitted_weights, weight_comparison = _refit_weights(scored, pillar_columns)
    fitted_k, fitted_base = _refit_calibration_curve(decile_table)

    summary_md = _render_summary(
        auc=auc,
        brier=brier,
        decile_table=decile_table,
        tier_table=tier_table,
        pillar_diff_table=pillar_diff_table,
        fitted_weights=fitted_weights,
        weight_comparison=weight_comparison,
        fitted_k=fitted_k,
        fitted_base=fitted_base,
        n_rows=len(scored),
        n_winners=int(scored["won_title"].sum()),
        pillar_columns=pillar_columns,
    )

    if write_files:
        OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
        SUMMARY_PATH.write_text(summary_md)
        _plot_calibration(decile_table, fitted_k, fitted_base, CALIBRATION_PATH)
        logger.info("wrote summary to %s", SUMMARY_PATH)
        logger.info("wrote plot to %s", CALIBRATION_PATH)

    return ValidationReport(
        auc=auc,
        brier=brier,
        decile_table=decile_table,
        tier_table=tier_table,
        pillar_diff_table=pillar_diff_table,
        fitted_weights=fitted_weights,
        weight_comparison=weight_comparison,
        fitted_k=fitted_k,
        fitted_base=fitted_base,
        n_rows=len(scored),
        n_winners=int(scored["won_title"].sum()),
        summary_md=summary_md,
    )


# ---------------------------------------------------------------------------
# Component statistics
# ---------------------------------------------------------------------------


def _detect_pillar_columns(scored: pd.DataFrame) -> list[str]:
    """Return numeric columns that look like pillars (not composites).

    ``path_viability`` is a unit-less multiplier (typically 0.4-1.6) applied
    to the base win-prob mapping, NOT a 0-100 pillar contributing to the
    composite. We exclude it from the logistic-regression refit so it does
    not get treated as a pillar weight.
    """
    excluded = {
        "championship_index",
        "win_probability",
        "multiplier_vs_base",
        "path_viability",
        "tier",
        "won_title",
        "season",
        "player_name",
        "team",
    }
    candidates: list[str] = []
    for c in scored.columns:
        if c in excluded:
            continue
        if pd.api.types.is_numeric_dtype(scored[c]):
            candidates.append(c)
    return candidates


def _compute_auc(scored: pd.DataFrame) -> float:
    """ROC-AUC of the composite index vs the binary won_title label."""
    from sklearn.metrics import roc_auc_score

    if scored["won_title"].nunique() < 2:
        logger.warning("won_title is constant -- AUC undefined")
        return float("nan")
    return float(roc_auc_score(scored["won_title"], scored["championship_index"]))


def _compute_brier(scored: pd.DataFrame) -> float:
    """Brier score of predicted win probability vs the binary label."""
    y = scored["won_title"].astype(float).to_numpy()
    p = scored["win_probability"].astype(float).to_numpy()
    return float(np.mean((p - y) ** 2))


def _decile_calibration(scored: pd.DataFrame) -> pd.DataFrame:
    """Bucket index into deciles and report predicted vs actual win rate.

    Uses ``pd.qcut`` with ``duplicates="drop"`` so heavily-skewed indexes
    (many rows clustered at index ~50 with the calculator's defaults)
    don't crash with non-unique bin edges.
    """
    sorted_df = scored.sort_values("championship_index").reset_index(drop=True)
    try:
        sorted_df["decile"] = pd.qcut(
            sorted_df["championship_index"], q=10, labels=False, duplicates="drop"
        )
    except ValueError:
        # All values identical -- single bucket
        sorted_df["decile"] = 0

    grouped = sorted_df.groupby("decile", observed=True).agg(
        n=("won_title", "size"),
        wins=("won_title", "sum"),
        mean_index=("championship_index", "mean"),
        mean_predicted=("win_probability", "mean"),
    )
    grouped["actual_win_rate"] = grouped["wins"] / grouped["n"]
    grouped = grouped.reset_index().rename(columns={"decile": "bucket"})
    grouped["bucket"] = grouped["bucket"].astype(int) + 1  # 1-indexed for readability
    return grouped[
        ["bucket", "n", "wins", "mean_index", "mean_predicted", "actual_win_rate"]
    ].copy()


def _tier_calibration(scored: pd.DataFrame) -> pd.DataFrame:
    """Win rate broken down by current production tier thresholds."""
    def to_tier(idx: float) -> str:
        for thresh, label in TIER_THRESHOLDS:
            if idx >= thresh:
                return label
        return "RAW PROSPECT"

    df = scored.copy()
    df["tier"] = df["championship_index"].apply(to_tier)
    grouped = df.groupby("tier").agg(
        n=("won_title", "size"),
        wins=("won_title", "sum"),
        mean_index=("championship_index", "mean"),
        mean_predicted=("win_probability", "mean"),
    )
    grouped["actual_win_rate"] = grouped["wins"] / grouped["n"]
    # Reindex by the canonical tier order
    order = [label for _, label in TIER_THRESHOLDS]
    grouped = grouped.reindex([t for t in order if t in grouped.index])
    return grouped.reset_index()


def _pillar_differential(
    scored: pd.DataFrame, pillar_columns: list[str]
) -> pd.DataFrame:
    """Mean pillar score for winners vs non-winners, plus Cohen's d."""
    rows: list[dict[str, Any]] = []
    winners = scored[scored["won_title"]]
    losers = scored[~scored["won_title"]]
    for col in pillar_columns:
        w = winners[col].dropna().astype(float)
        l = losers[col].dropna().astype(float)
        if len(w) < 2 or len(l) < 2:
            cohens_d = float("nan")
        else:
            pooled_sd = np.sqrt(((w.std() ** 2) + (l.std() ** 2)) / 2)
            cohens_d = (w.mean() - l.mean()) / pooled_sd if pooled_sd > 0 else 0.0
        rows.append(
            {
                "pillar": col,
                "winner_mean": float(w.mean()) if len(w) else float("nan"),
                "loser_mean": float(l.mean()) if len(l) else float("nan"),
                "diff": (
                    float(w.mean() - l.mean()) if len(w) and len(l) else float("nan")
                ),
                "cohens_d": float(cohens_d),
            }
        )
    return pd.DataFrame(rows)


def _refit_weights(
    scored: pd.DataFrame, pillar_columns: list[str]
) -> tuple[dict[str, float], pd.DataFrame]:
    """Logistic-regression refit of pillar weights.

    Returns
    -------
    fitted_weights:
        Dict mapping pillar -> normalised positive weight (sum = 1.0).
        Computed as ``|coef| * std(feature)`` then normalised.
    weight_comparison:
        DataFrame comparing current vs empirical weights side-by-side.
    """
    from sklearn.linear_model import LogisticRegression

    X = scored[pillar_columns].astype(float).fillna(50.0).to_numpy()
    y = scored["won_title"].astype(int).to_numpy()

    if len(np.unique(y)) < 2:
        logger.warning("won_title is constant -- skipping logistic refit")
        zero = {p: 0.0 for p in pillar_columns}
        return zero, pd.DataFrame(
            {"pillar": pillar_columns, "current": 0.0, "empirical": 0.0}
        )

    lr = LogisticRegression(class_weight="balanced", penalty="l2", C=1.0, max_iter=1000)
    lr.fit(X, y)
    raw_coefs = lr.coef_[0]
    feature_stds = X.std(axis=0)
    standardised = np.abs(raw_coefs) * feature_stds
    total = standardised.sum()
    if total <= 0:
        norm_weights = np.full_like(standardised, 1.0 / len(pillar_columns))
    else:
        norm_weights = standardised / total

    fitted_weights = {p: float(w) for p, w in zip(pillar_columns, norm_weights)}

    if "supporting_cast" in pillar_columns:
        current = CURRENT_WEIGHTS_7
    else:
        current = CURRENT_WEIGHTS_6
    comparison_rows = [
        {
            "pillar": p,
            "current_weight": current.get(p, float("nan")),
            "empirical_weight": fitted_weights.get(p, float("nan")),
            "delta": fitted_weights.get(p, 0.0) - current.get(p, 0.0),
        }
        for p in pillar_columns
    ]
    return fitted_weights, pd.DataFrame(comparison_rows)


def _refit_calibration_curve(decile_table: pd.DataFrame) -> tuple[float, float]:
    """Fit ``actual_win_rate ~ base * exp(k * (mean_index - 50))``.

    Args:
        decile_table: Output of :func:`_decile_calibration`.

    Returns:
        ``(k, base)`` -- the steepness factor and base rate that best fit
        the observed decile win rates.
    """
    from scipy.optimize import curve_fit

    if decile_table.empty:
        return float("nan"), float("nan")

    def model(x: np.ndarray, k: float, base: float) -> np.ndarray:
        return base * np.exp(k * (x - 50.0))

    xdata = decile_table["mean_index"].to_numpy(dtype=float)
    ydata = decile_table["actual_win_rate"].to_numpy(dtype=float)

    if len(xdata) < 2 or np.allclose(ydata, 0):
        # Not enough variation -- return current production values.
        return CURRENT_K, HISTORICAL_BASE_RATE
    try:
        popt, _ = curve_fit(
            model,
            xdata,
            ydata,
            p0=[CURRENT_K, HISTORICAL_BASE_RATE],
            bounds=([0.0, 1e-5], [0.5, 1.0]),
            maxfev=5000,
        )
        return float(popt[0]), float(popt[1])
    except Exception as exc:
        logger.warning("calibration refit failed: %s", exc)
        return CURRENT_K, HISTORICAL_BASE_RATE


# ---------------------------------------------------------------------------
# Output rendering
# ---------------------------------------------------------------------------


def _render_summary(
    *,
    auc: float,
    brier: float,
    decile_table: pd.DataFrame,
    tier_table: pd.DataFrame,
    pillar_diff_table: pd.DataFrame,
    fitted_weights: dict[str, float],
    weight_comparison: pd.DataFrame,
    fitted_k: float,
    fitted_base: float,
    n_rows: int,
    n_winners: int,
    pillar_columns: list[str],
) -> str:
    """Build a Markdown report from the computed statistics."""
    lines: list[str] = []
    lines.append("# Championship Index Backtest")
    lines.append("")
    lines.append(
        f"Sample: **{n_rows}** player-seasons, **{n_winners}** title wins."
    )
    lines.append(f"Pillar columns detected: `{pillar_columns}`")
    lines.append("")
    lines.append("## Headline metrics")
    lines.append("")
    lines.append(f"- AUC (index vs won_title): **{auc:.3f}**")
    lines.append(f"- Brier score (predicted prob vs label): **{brier:.4f}**")
    lines.append("")
    lines.append("## Decile calibration")
    lines.append("")
    lines.append(decile_table.round(4).to_markdown(index=False))
    lines.append("")
    lines.append("## Tier confusion")
    lines.append("")
    lines.append(tier_table.round(4).to_markdown(index=False))
    lines.append("")
    lines.append("## Per-pillar differential (winners vs others)")
    lines.append("")
    lines.append(pillar_diff_table.round(3).to_markdown(index=False))
    lines.append("")
    lines.append("## Empirical weights vs current weights")
    lines.append("")
    lines.append(weight_comparison.round(3).to_markdown(index=False))
    lines.append("")
    lines.append("## Recalibrated win-probability mapping")
    lines.append("")
    lines.append(
        f"- Current production: `prob = {HISTORICAL_BASE_RATE:.3f} * "
        f"exp({CURRENT_K} * (index - 50))`"
    )
    lines.append(
        f"- Empirical refit:     `prob = {fitted_base:.4f} * "
        f"exp({fitted_k:.4f} * (index - 50))`"
    )
    lines.append("")
    lines.append("![Calibration curve](calibration.png)")
    lines.append("")
    lines.append("---")
    lines.append(
        "Reproduce by running `python -m scripts.champ_backtest.cli all` from "
        "`backend/`. Synthetic test data may be substituted via the `--demo` "
        "flag for plumbing checks. Real validation requires the full collect/score/validate sweep."
    )
    return "\n".join(lines) + "\n"


def _plot_calibration(
    decile_table: pd.DataFrame,
    fitted_k: float,
    fitted_base: float,
    out_path: Path,
) -> None:
    """Render a calibration plot: deciles vs predicted/actual win rates."""
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fig, ax = plt.subplots(figsize=(8, 5))
    if not decile_table.empty:
        ax.scatter(
            decile_table["mean_index"],
            decile_table["actual_win_rate"],
            label="observed (decile mean)",
            color="#1f77b4",
            s=60,
        )
        ax.plot(
            decile_table["mean_index"],
            decile_table["mean_predicted"],
            label="current model prediction",
            color="#d62728",
            linestyle="--",
        )
        # Refit curve
        xx = np.linspace(
            decile_table["mean_index"].min(), decile_table["mean_index"].max(), 200
        )
        yy = fitted_base * np.exp(fitted_k * (xx - 50.0))
        ax.plot(xx, yy, label="empirical refit", color="#2ca02c")

    ax.set_xlabel("Championship Index (decile mean)")
    ax.set_ylabel("Title win rate")
    ax.set_title("Calibration: predicted vs actual win rate by decile")
    ax.legend()
    ax.grid(alpha=0.3)
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    plt.close(fig)
