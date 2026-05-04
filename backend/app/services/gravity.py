"""Canonical gravity index implementation.

Computes the gravity index from four positionally-normalised, Bayesian-shrunk
components and maps them through the standard normal CDF:

    gravity_index = 100 * Phi( 0.40*z(off_ball)
                             + 0.30*z(teammate_lift)
                             + 0.20*z(on_ball)
                             + 0.10*z(rim_pressure_pen) )

This single entry point replaces two prior implementations:

- ``portability._gravity_score`` (4-component weighted average dominated by
  self-creation signals — pull-up 3PA, AST ratio, PPT — which double-counted
  with the Self-Creation sub-score's other inputs).
- ``player_card._build_gravity_index`` (60/40 mix of tight_attention_rate
  and team_off_lift, no positional context).

By centralising here, gravity becomes off-ball-first (matching the
basketball intuition that gravity is what defenses pay you to *not* hold
the ball), and self-creation signals stay in their original Self-Creation
roles without leaking into gravity.

Position normalisation and Bayesian shrinkage protect low-volume players
from extreme scores: a rookie wing with 30 catch-and-shoot looks should
land near the league average for wings, not at the 99th percentile.
"""

from __future__ import annotations

import math
from collections.abc import Mapping, Sequence
from dataclasses import dataclass

from app.services.metrics_utils import map_position_to_bucket, safe_div, safe_float

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

# Component weights inside the pre-Phi linear combination. Off-ball is the
# heaviest because gravity is operationally defined by where defenders go
# when the player does NOT have the ball.
WEIGHT_OFF_BALL: float = 0.40
WEIGHT_TEAMMATE_LIFT: float = 0.30
WEIGHT_ON_BALL: float = 0.20
WEIGHT_RIM_PRESSURE: float = 0.10

# Bayesian shrinkage strength k. Two regimes:
#   - SHOT_VOLUME_K applies to components driven by per-shot observations
#     (off-ball and on-ball) — units are FGA.
#   - MINUTES_K applies to components driven by lineup-level on/off splits
#     (teammate_lift) — units are on-court minutes.
# The rim-pressure component is a pre-normalised composite and uses
# SHOT_VOLUME_K with a synthetic n drawn from drives + paint touches.
SHOT_VOLUME_K: float = 200.0
MINUTES_K: float = 600.0

# League-wide fallback distributions used when ``league_distributions``
# does not include a positional bucket. Means and stdevs are rough
# estimates from recent NBA seasons; used only as a last-resort prior so
# the score never collapses to NaN for a fresh-season player pool.
_FALLBACK_DISTRIBUTION = {"mean": 0.0, "std": 1.0}

# Components and the composite are all mapped through Phi (standard normal
# CDF). The output of Phi(z) is in [0, 1], multiplied by 100 to land on the
# 0-100 grade scale used by the rest of the codebase.


# ---------------------------------------------------------------------------
# Result dataclass
# ---------------------------------------------------------------------------


@dataclass
class GravityComponents:
    """Raw and shrunk component values plus the final 0-100 gravity index.

    Stored separately from the index itself so callers (Self-Creation
    sub-score, player-card gravity panel) can surface the underlying
    inputs in UI / debugging without recomputing them.
    """

    off_ball: float
    teammate_lift: float
    on_ball: float
    rim_pressure_pen: float
    gravity_index: float


# ---------------------------------------------------------------------------
# Numerical helpers
# ---------------------------------------------------------------------------


def _phi(z: float) -> float:
    """Standard normal CDF via ``math.erf`` (no scipy dep at runtime).

    Equivalent to ``scipy.stats.norm.cdf(z)`` to within float precision.
    """
    return 0.5 * (1.0 + math.erf(z / math.sqrt(2.0)))


def _shrink(observed: float, n: float, k: float, prior: float) -> float:
    """Bayesian shrinkage toward ``prior`` with prior-weight ``k``.

    Replaces brittle ``if poss < MIN: return 40.0`` early-returns with a
    smooth interpolation: low-n observations end up close to the
    positional mean, high-n observations dominate the posterior.
    """
    n = max(0.0, n)
    if n + k <= 0:
        return prior
    return (n / (n + k)) * observed + (k / (n + k)) * prior


def _z(value: float, mean: float, std: float) -> float:
    """Z-score with a stdev floor to avoid divide-by-zero on flat dists."""
    if std <= 1e-9:
        return 0.0
    return (value - mean) / std


def _dist_for(
    league_distributions: Mapping[str, Mapping[str, Mapping[str, float]]] | None,
    component: str,
    bucket: str,
) -> Mapping[str, float]:
    """Look up ``{mean, std}`` for ``(component, bucket)`` with fallback."""
    if not league_distributions:
        return _FALLBACK_DISTRIBUTION
    by_bucket = league_distributions.get(component) or {}
    return by_bucket.get(bucket) or by_bucket.get("ALL") or _FALLBACK_DISTRIBUTION


# ---------------------------------------------------------------------------
# Component computations (raw, pre-shrinkage)
# ---------------------------------------------------------------------------


def _raw_off_ball(
    *,
    tight_attention_rate: float,
    catch_shoot_fga: float,
    total_fga: float,
) -> tuple[float, float]:
    """Off-ball gravity raw value + sample size (FGA).

    Approximation: tight_attention_rate * catch-and-shoot share of FGA.
    A high-CS3 shooter who is also closely guarded is exactly the
    archetype defenses respect off the ball (Curry, Klay, Korver).

    Returns:
        (value, n) where n is total FGA — the volume-weighted sample
        size driving Bayesian shrinkage.
    """
    cs_share = safe_div(catch_shoot_fga, total_fga)
    value = tight_attention_rate * cs_share
    return value, total_fga


def _raw_teammate_lift(
    *,
    team_open3_freq_diff: float,
    team_efg_diff: float,
    on_court_minutes: float,
) -> tuple[float, float]:
    """Teammate-lift raw value + sample size (on-court minutes).

    Weighted 60/40 toward the open-3 lift because defender-distance
    splits are a more direct gravity proxy than overall eFG (which is
    confounded by self-creation efficiency).
    """
    value = 0.6 * team_open3_freq_diff + 0.4 * team_efg_diff
    return value, on_court_minutes


def _raw_on_ball(
    *,
    tight_attention_rate: float,
    pullup_fga: float,
    total_fga: float,
    drive_pf: float,
    drives: float,
) -> tuple[float, float]:
    """On-ball gravity raw value + sample size (FGA).

    Two pieces:
    - Tight-attention concentrated on pull-up shots: defenders crowd
      pull-up artists who can punish from range.
    - Drive PF rate: fouls drawn per drive measure how reluctant
      defenders are to fully commit.
    """
    pu_share = safe_div(pullup_fga, total_fga)
    drive_pf_rate = safe_div(drive_pf, drives)
    value = 0.7 * (tight_attention_rate * pu_share) + 0.3 * drive_pf_rate
    return value, total_fga


def _raw_rim_pressure(
    *,
    rim_gravity_score: float,
    drives: float,
    paint_touches: float,
) -> tuple[float, float]:
    """Rim-pressure raw value (already 0-1) + synthetic sample size.

    ``rim_gravity_score`` is the ``_build_rim_gravity`` output on a
    0-100 scale; we divide by 100 to land on [0, 1] before z-scoring.
    Sample size is drives + paint touches per game scaled to a season
    estimate, so a deep bench big with 2 paint touches per game gets
    pulled hard toward the prior.
    """
    value = max(0.0, min(1.0, rim_gravity_score / 100.0))
    # Per-game stats * 70 games yields a season-scale n in the same
    # ballpark as total FGA, keeping SHOT_VOLUME_K well-calibrated
    # across components.
    n = (drives + paint_touches) * 70.0
    return value, n


# ---------------------------------------------------------------------------
# Public entry point
# ---------------------------------------------------------------------------


def compute_gravity(
    *,
    position: str | None,
    # Off-ball inputs
    tight_attention_rate: float,
    catch_shoot_fga: float,
    total_fga: float,
    # Teammate-lift inputs
    team_open3_freq_diff: float,
    team_efg_diff: float,
    on_court_minutes: float,
    # On-ball inputs
    pullup_fga: float,
    drive_pf: float,
    drives: float,
    # Rim-pressure input (already a 0-100 composite)
    rim_gravity_score: float,
    # Optional: include paint touches in rim n if available
    paint_touches: float = 0.0,
    # Positional league distributions: {component: {bucket: {mean, std}}}
    league_distributions: Mapping[str, Mapping[str, Mapping[str, float]]] | None = None,
) -> GravityComponents:
    """Compute the canonical 0-100 gravity index for a player.

    Each component is:
      1. Computed as a raw value + sample size (n).
      2. Shrunk toward its positional mean with prior weight ``k`` (200 for
         shot-volume components, 600 for the minutes-driven teammate lift).
      3. Z-scored against the positional distribution.
      4. Linearly combined with the published weights.
      5. Mapped through Phi to [0, 1] and scaled to [0, 100].

    All ``float``-typed inputs accept ``Decimal`` via ``safe_float`` so
    callers can pass ORM column values directly without conversion.

    Args:
        position: NBA-API position string (e.g. ``"PG"``). Used to pick
            the per-bucket distribution; defaults to ``"W"`` when missing.
        tight_attention_rate: Share of player's FGA with a defender < 4ft.
        catch_shoot_fga: Player's catch-and-shoot FGA per game.
        total_fga: Player's total FGA per game.
        team_open3_freq_diff: ``team_open3_freq_diff`` from
            :class:`PlayerOnOffShooting` (on - off).
        team_efg_diff: ``team_efg_diff`` from :class:`PlayerOnOffShooting`.
        on_court_minutes: On-court minutes (sample-size signal for the
            teammate-lift component).
        pullup_fga: Player's pull-up FGA per game.
        drive_pf: Personal fouls drawn on drives per game.
        drives: Total drives per game.
        rim_gravity_score: Existing 0-100 rim-gravity composite.
        paint_touches: Paint touches per game (folded into rim n).
        league_distributions: Positional ``{component: {bucket: {mean,
            std}}}`` distribution map. When absent, falls back to a
            standard-normal prior (mean 0, std 1) and gravity collapses
            to ``Phi(weighted_sum_of_raw_shrunk_values) * 100``.

    Returns:
        A :class:`GravityComponents` with shrunk component values and
        the final ``gravity_index`` on [0, 100].
    """
    bucket = map_position_to_bucket(position)

    # 1. Raw values + sample sizes.
    raw_ob, n_ob = _raw_off_ball(
        tight_attention_rate=safe_float(tight_attention_rate),
        catch_shoot_fga=safe_float(catch_shoot_fga),
        total_fga=safe_float(total_fga),
    )
    raw_tl, n_tl = _raw_teammate_lift(
        team_open3_freq_diff=safe_float(team_open3_freq_diff),
        team_efg_diff=safe_float(team_efg_diff),
        on_court_minutes=safe_float(on_court_minutes),
    )
    raw_onb, n_onb = _raw_on_ball(
        tight_attention_rate=safe_float(tight_attention_rate),
        pullup_fga=safe_float(pullup_fga),
        total_fga=safe_float(total_fga),
        drive_pf=safe_float(drive_pf),
        drives=safe_float(drives),
    )
    raw_rim, n_rim = _raw_rim_pressure(
        rim_gravity_score=safe_float(rim_gravity_score),
        drives=safe_float(drives),
        paint_touches=safe_float(paint_touches),
    )

    # 2. Shrink toward positional mean (the prior).
    dist_ob = _dist_for(league_distributions, "off_ball", bucket)
    dist_tl = _dist_for(league_distributions, "teammate_lift", bucket)
    dist_onb = _dist_for(league_distributions, "on_ball", bucket)
    dist_rim = _dist_for(league_distributions, "rim_pressure", bucket)

    shrunk_ob = _shrink(raw_ob, n_ob, SHOT_VOLUME_K, dist_ob["mean"])
    shrunk_tl = _shrink(raw_tl, n_tl, MINUTES_K, dist_tl["mean"])
    shrunk_onb = _shrink(raw_onb, n_onb, SHOT_VOLUME_K, dist_onb["mean"])
    shrunk_rim = _shrink(raw_rim, n_rim, SHOT_VOLUME_K, dist_rim["mean"])

    # 3. Position-relative z-scores.
    z_ob = _z(shrunk_ob, dist_ob["mean"], dist_ob["std"])
    z_tl = _z(shrunk_tl, dist_tl["mean"], dist_tl["std"])
    z_onb = _z(shrunk_onb, dist_onb["mean"], dist_onb["std"])
    z_rim = _z(shrunk_rim, dist_rim["mean"], dist_rim["std"])

    # 4. Weighted linear combination.
    z_combined = (
        WEIGHT_OFF_BALL * z_ob
        + WEIGHT_TEAMMATE_LIFT * z_tl
        + WEIGHT_ON_BALL * z_onb
        + WEIGHT_RIM_PRESSURE * z_rim
    )

    # 5. Phi -> [0, 100].
    gravity_index = 100.0 * _phi(z_combined)

    return GravityComponents(
        off_ball=shrunk_ob,
        teammate_lift=shrunk_tl,
        on_ball=shrunk_onb,
        rim_pressure_pen=shrunk_rim,
        gravity_index=gravity_index,
    )


# ---------------------------------------------------------------------------
# League-distribution builder
# ---------------------------------------------------------------------------


def build_league_distributions(
    samples: Sequence[Mapping[str, float | str | None]],
) -> dict[str, dict[str, dict[str, float]]]:
    """Build per-component, per-bucket ``{mean, std}`` from a sample list.

    Each sample is a dict with the same keys as :func:`compute_gravity`'s
    inputs plus ``"position"``. Used by the orchestrator to compute
    season-level distributions once and pass them into every per-player
    :func:`compute_gravity` call (mirrors the
    ``portability.league_distributions`` pattern).

    Bucket ``"ALL"`` is always populated and acts as the fallback prior
    for under-represented buckets.
    """
    by_component: dict[str, dict[str, list[float]]] = {
        "off_ball": {},
        "teammate_lift": {},
        "on_ball": {},
        "rim_pressure": {},
    }

    def _push(comp: str, bucket: str, value: float) -> None:
        by_component[comp].setdefault(bucket, []).append(value)
        by_component[comp].setdefault("ALL", []).append(value)

    for s in samples:
        position = s.get("position")
        bucket = map_position_to_bucket(position if isinstance(position, str) else None)

        ob, _ = _raw_off_ball(
            tight_attention_rate=safe_float(s.get("tight_attention_rate")),
            catch_shoot_fga=safe_float(s.get("catch_shoot_fga")),
            total_fga=safe_float(s.get("total_fga")),
        )
        tl, _ = _raw_teammate_lift(
            team_open3_freq_diff=safe_float(s.get("team_open3_freq_diff")),
            team_efg_diff=safe_float(s.get("team_efg_diff")),
            on_court_minutes=safe_float(s.get("on_court_minutes")),
        )
        onb, _ = _raw_on_ball(
            tight_attention_rate=safe_float(s.get("tight_attention_rate")),
            pullup_fga=safe_float(s.get("pullup_fga")),
            total_fga=safe_float(s.get("total_fga")),
            drive_pf=safe_float(s.get("drive_pf")),
            drives=safe_float(s.get("drives")),
        )
        rim, _ = _raw_rim_pressure(
            rim_gravity_score=safe_float(s.get("rim_gravity_score")),
            drives=safe_float(s.get("drives")),
            paint_touches=safe_float(s.get("paint_touches")),
        )

        _push("off_ball", bucket, ob)
        _push("teammate_lift", bucket, tl)
        _push("on_ball", bucket, onb)
        _push("rim_pressure", bucket, rim)

    out: dict[str, dict[str, dict[str, float]]] = {}
    for comp, buckets in by_component.items():
        out[comp] = {}
        for bucket, values in buckets.items():
            if not values:
                continue
            mean = sum(values) / len(values)
            var = sum((v - mean) ** 2 for v in values) / len(values)
            std = math.sqrt(var) if var > 0 else 1e-6
            out[comp][bucket] = {"mean": mean, "std": std}
    return out
