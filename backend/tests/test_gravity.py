"""Unit tests for the canonical gravity index in :mod:`app.services.gravity`.

Three behaviours are pinned down:

1. **Archetype ordering** -- a Curry-like off-ball + teammate-lift profile
   ranks higher than a pure shooter (Duncan Robinson) which in turn
   ranks higher than a low-gravity bench big.
2. **Shrinkage on low-volume players** -- a player with very few shot
   attempts must not get an extreme score; Bayesian shrinkage pulls them
   toward the positional mean.
3. **Phi-mapping properties** -- the index always sits in [0, 100] and a
   purely-mean profile lands at 50.

All fixtures are synthetic dicts; nothing hits the database.
"""

from __future__ import annotations

import math
from typing import Any

import pytest

from app.services.gravity import (
    GravityComponents,
    build_league_distributions,
    compute_gravity,
)

# ---------------------------------------------------------------------------
# Synthetic player profiles
# ---------------------------------------------------------------------------

# Curry-like: tons of catch-and-shoot 3s, defenders glued to him, and the
# Warriors' team eFG craters when he sits. Plays guard.
_CURRY: dict[str, Any] = {
    "position": "PG",
    "tight_attention_rate": 0.55,
    "catch_shoot_fga": 6.0,
    "total_fga": 19.0,
    "team_open3_freq_diff": 0.05,
    "team_efg_diff": 0.04,
    "on_court_minutes": 2200.0,
    "pullup_fga": 8.5,
    "drive_pf": 1.8,
    "drives": 7.5,
    "rim_gravity_score": 35.0,
    "paint_touches": 3.0,
}

# Duncan-Robinson-like: pure spot-up shooter, high CS3 share, very high
# tight attention because he's a 40% bombing threat, but limited
# self-creation and modest team eFG lift (he doesn't bend the geometry
# the way Curry does over a 36-min sample).
_DUNCAN: dict[str, Any] = {
    "position": "SG",
    "tight_attention_rate": 0.50,
    "catch_shoot_fga": 5.5,
    "total_fga": 9.0,
    "team_open3_freq_diff": 0.015,
    "team_efg_diff": 0.012,
    "on_court_minutes": 1500.0,
    "pullup_fga": 0.6,
    "drive_pf": 0.4,
    "drives": 1.2,
    "rim_gravity_score": 15.0,
    "paint_touches": 0.5,
}

# Bench big: low attention, takes few shots (mostly putbacks), modest
# rim pressure but no spacing or creation gravity at all.
_BENCH_BIG: dict[str, Any] = {
    "position": "C",
    "tight_attention_rate": 0.18,
    "catch_shoot_fga": 0.2,
    "total_fga": 4.5,
    "team_open3_freq_diff": -0.01,
    "team_efg_diff": -0.005,
    "on_court_minutes": 700.0,
    "pullup_fga": 0.1,
    "drive_pf": 0.2,
    "drives": 1.0,
    "rim_gravity_score": 30.0,
    "paint_touches": 4.0,
}

# League sample used to derive positional distributions. Each bucket
# gets a handful of players spanning the realistic range so the z-scores
# end up sensible.
def _league_sample() -> list[dict[str, Any]]:
    """Build a representative synthetic league sample."""
    sample: list[dict[str, Any]] = []

    # Guards -- mix of high-gravity shooters and low-gravity rim attackers.
    for i in range(8):
        sample.append(
            {
                "position": "PG",
                "tight_attention_rate": 0.30 + 0.04 * i,
                "catch_shoot_fga": 1.0 + 0.7 * i,
                "total_fga": 10.0 + 0.5 * i,
                "team_open3_freq_diff": -0.02 + 0.01 * i,
                "team_efg_diff": -0.02 + 0.008 * i,
                "on_court_minutes": 1500.0,
                "pullup_fga": 1.0 + 0.5 * i,
                "drive_pf": 0.5 + 0.15 * i,
                "drives": 4.0 + 0.5 * i,
                "rim_gravity_score": 20.0 + 4.0 * i,
                "paint_touches": 1.0 + 0.5 * i,
            }
        )

    # Wings -- spot-up shooters and slashers.
    for i in range(8):
        sample.append(
            {
                "position": "SG",
                "tight_attention_rate": 0.28 + 0.04 * i,
                "catch_shoot_fga": 2.0 + 0.5 * i,
                "total_fga": 8.0 + 0.6 * i,
                "team_open3_freq_diff": -0.01 + 0.005 * i,
                "team_efg_diff": -0.01 + 0.004 * i,
                "on_court_minutes": 1400.0,
                "pullup_fga": 0.5 + 0.3 * i,
                "drive_pf": 0.3 + 0.1 * i,
                "drives": 2.0 + 0.5 * i,
                "rim_gravity_score": 15.0 + 4.0 * i,
                "paint_touches": 0.8 + 0.4 * i,
            }
        )

    # Bigs -- mostly rim-bound, low spacing.
    for i in range(8):
        sample.append(
            {
                "position": "C",
                "tight_attention_rate": 0.18 + 0.03 * i,
                "catch_shoot_fga": 0.1 + 0.1 * i,
                "total_fga": 5.0 + 0.5 * i,
                "team_open3_freq_diff": -0.005 + 0.003 * i,
                "team_efg_diff": -0.01 + 0.003 * i,
                "on_court_minutes": 1300.0,
                "pullup_fga": 0.05 + 0.05 * i,
                "drive_pf": 0.2 + 0.1 * i,
                "drives": 1.5 + 0.4 * i,
                "rim_gravity_score": 25.0 + 5.0 * i,
                "paint_touches": 3.0 + 1.0 * i,
            }
        )

    return sample


@pytest.fixture()
def league_distributions() -> dict[str, dict[str, dict[str, float]]]:
    return build_league_distributions(_league_sample())


# ---------------------------------------------------------------------------
# Archetype ordering
# ---------------------------------------------------------------------------


def test_curry_like_outranks_duncan_robinson_like_outranks_bench_big(
    league_distributions: dict[str, dict[str, dict[str, float]]],
) -> None:
    """The intended ordering: Curry > Duncan Robinson > bench big."""
    curry = compute_gravity(**_CURRY, league_distributions=league_distributions)
    duncan = compute_gravity(**_DUNCAN, league_distributions=league_distributions)
    big = compute_gravity(**_BENCH_BIG, league_distributions=league_distributions)

    assert isinstance(curry, GravityComponents)
    assert isinstance(duncan, GravityComponents)
    assert isinstance(big, GravityComponents)

    assert curry.gravity_index > duncan.gravity_index, (
        f"Curry-like ({curry.gravity_index:.1f}) should outrank Duncan "
        f"Robinson-like ({duncan.gravity_index:.1f})"
    )
    assert duncan.gravity_index > big.gravity_index, (
        f"Duncan Robinson-like ({duncan.gravity_index:.1f}) should outrank "
        f"a bench big ({big.gravity_index:.1f})"
    )


def test_curry_off_ball_dominates_bench_big_off_ball(
    league_distributions: dict[str, dict[str, dict[str, float]]],
) -> None:
    """Off-ball component is the gravity headline -- Curry should crush a big."""
    curry = compute_gravity(**_CURRY, league_distributions=league_distributions)
    big = compute_gravity(**_BENCH_BIG, league_distributions=league_distributions)
    assert curry.off_ball > big.off_ball


# ---------------------------------------------------------------------------
# Bayesian shrinkage on low-volume players
# ---------------------------------------------------------------------------


def test_low_volume_player_pulled_toward_mean(
    league_distributions: dict[str, dict[str, dict[str, float]]],
) -> None:
    """A 30-shot rookie with elite-looking rates does NOT get an extreme score."""
    low_volume_curry_clone = {
        **_CURRY,
        # Same shot-mix percentages as Curry, but tiny per-game volumes.
        "catch_shoot_fga": 0.5,
        "total_fga": 1.5,
        "pullup_fga": 0.7,
        "drives": 0.6,
        "drive_pf": 0.15,
        "on_court_minutes": 80.0,  # ~10 games at light minutes
    }
    full_volume = compute_gravity(
        **_CURRY, league_distributions=league_distributions
    )
    shrunk = compute_gravity(
        **low_volume_curry_clone, league_distributions=league_distributions
    )

    # Shrunk score should be (a) less extreme than the full-volume Curry
    # and (b) closer to the league baseline of 50.
    assert (
        abs(shrunk.gravity_index - 50.0) < abs(full_volume.gravity_index - 50.0)
    ), (
        f"Low-volume profile ({shrunk.gravity_index:.1f}) should be closer "
        f"to 50 than full-volume Curry ({full_volume.gravity_index:.1f})"
    )

    # And in absolute terms a player with ~30 shots should not approach
    # the 95th-percentile-ish range that real-Curry inhabits.
    assert shrunk.gravity_index < 90.0, (
        f"Low-volume score {shrunk.gravity_index:.1f} is unreasonably "
        "extreme -- shrinkage failed"
    )


def test_zero_minute_player_collapses_to_prior(
    league_distributions: dict[str, dict[str, dict[str, float]]],
) -> None:
    """An n=0 player should land essentially at the positional mean (50)."""
    empty = {
        "position": "PG",
        "tight_attention_rate": 0.0,
        "catch_shoot_fga": 0.0,
        "total_fga": 0.0,
        "team_open3_freq_diff": 0.0,
        "team_efg_diff": 0.0,
        "on_court_minutes": 0.0,
        "pullup_fga": 0.0,
        "drive_pf": 0.0,
        "drives": 0.0,
        "rim_gravity_score": 0.0,
        "paint_touches": 0.0,
    }
    components = compute_gravity(**empty, league_distributions=league_distributions)
    # With no observed data, every component shrinks to its positional
    # mean -> z=0 across the board -> Phi(0) * 100 = 50.
    assert math.isclose(components.gravity_index, 50.0, abs_tol=1.0)


# ---------------------------------------------------------------------------
# Output range and Phi-mapping properties
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("profile", [_CURRY, _DUNCAN, _BENCH_BIG])
def test_index_always_in_zero_to_one_hundred(
    profile: dict[str, Any],
    league_distributions: dict[str, dict[str, dict[str, float]]],
) -> None:
    """Phi maps to [0, 1], so 100 * Phi must land on [0, 100]."""
    c = compute_gravity(**profile, league_distributions=league_distributions)
    assert 0.0 <= c.gravity_index <= 100.0


def test_no_distributions_falls_back_to_unit_normal_prior() -> None:
    """When league_distributions is absent the function should still produce a sane score."""
    c = compute_gravity(**_CURRY, league_distributions=None)
    assert isinstance(c, GravityComponents)
    assert 0.0 <= c.gravity_index <= 100.0


def test_components_returned_alongside_index(
    league_distributions: dict[str, dict[str, dict[str, float]]],
) -> None:
    """All four shrunk component values are exposed for UI / debugging."""
    c = compute_gravity(**_CURRY, league_distributions=league_distributions)
    assert c.off_ball is not None
    assert c.teammate_lift is not None
    assert c.on_ball is not None
    assert c.rim_pressure_pen is not None
