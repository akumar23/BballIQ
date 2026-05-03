"""Championship Index service.

Computes a 0-100 composite score evaluating whether a player can lead
a team to a championship as the #1 option. Synthesizes six weighted
pillars derived from available stats. A separate ``path_viability``
multiplier scales the resulting championship win probability based on
supporting-cast strength (it does NOT modify the index itself).

Pillars and weights:
1. Playoff Scoring Projection (27%)
2. Two-Way Impact (23%)
3. Clutch & Pressure Performance (15%)
4. Portability / Roster Flexibility (15%)
5. Durability & Availability (10%)
6. Playoff Experience & Growth Arc (10%)
"""

from __future__ import annotations

import logging
import math
from dataclasses import dataclass
from typing import Any

from app.services.metrics_utils import normalize_to_0_100, safe_div, safe_float

logger = logging.getLogger(__name__)

# Championship tier thresholds
TIERS = [
    (90, "CHAMPIONSHIP ALPHA"),
    (80, "FUTURE ALPHA"),
    (70, "FLAWED ALPHA"),
    (60, "EMERGING ALPHA"),
    (45, "CHAMPIONSHIP PIECE"),
    (0, "RAW PROSPECT"),
]

# Historical base rate: ~3.3% chance any #1 option wins a title in a given year
HISTORICAL_BASE_RATE = 0.033

# Equivalent prior sample size (in true-shooting attempts) for clutch shrinkage.
# 200 TSA approximates ~1 full season of clutch volume for a high-usage star;
# with this prior, a 50-80 possession clutch sample shrinks ~70% toward the
# regular-season TS%, which matches observed year-over-year clutch noise.
CLUTCH_PRIOR_STRENGTH = 200

# Per-zone playoff TS%-point drops (regular-season TS% minus playoff TS%).
# Calibrated from public playoff vs regular-season splits: rim attempts get
# walled off the most by playoff length/help, midrange is least affected,
# and 3PT outcomes depend on whether the look is self-generated or kicked.
RIM_PLAYOFF_TS_DROP = 0.030
MIDRANGE_PLAYOFF_TS_DROP = 0.008
THREE_SELF_CREATED_PLAYOFF_TS_DROP = 0.020
THREE_SPOT_UP_PLAYOFF_TS_DROP = 0.010


@dataclass
class ChampionshipResult:
    """Complete championship index analysis."""

    # Pillar scores (0-100)
    playoff_scoring: float = 50.0
    two_way_impact: float = 50.0
    clutch_performance: float = 50.0
    portability: float = 50.0
    durability: float = 50.0
    experience_arc: float = 50.0

    # Final composite
    championship_index: float = 50.0
    tier: str = "CHAMPIONSHIP PIECE"
    win_probability: float = 0.033
    multiplier_vs_base: float = 1.0
    # Supporting-cast multiplier applied to win probability (not the index).
    path_viability: float = 1.0

    def __post_init__(self) -> None:
        self.championship_index = round(
            self.playoff_scoring * 0.27
            + self.two_way_impact * 0.23
            + self.clutch_performance * 0.15
            + self.portability * 0.15
            + self.durability * 0.10
            + self.experience_arc * 0.10,
            1,
        )
        self.tier = _index_to_tier(self.championship_index)
        base_prob = _index_to_win_prob(self.championship_index)
        self.win_probability = round(
            min(0.30, base_prob * self.path_viability), 4
        )
        self.multiplier_vs_base = round(
            self.win_probability / HISTORICAL_BASE_RATE, 1
        )


def _index_to_tier(index: float) -> str:
    for threshold, label in TIERS:
        if index >= threshold:
            return label
    return "RAW PROSPECT"


def _index_to_win_prob(index: float) -> float:
    """Map championship index to estimated annual win probability.

    Scale: index 100 -> ~15% chance, index 50 -> ~3.3%, index 0 -> ~0.5%
    Uses exponential scaling to model diminishing returns at the top.
    """
    k = 0.03  # Steepness factor
    prob = HISTORICAL_BASE_RATE * math.exp(k * (index - 50))
    return round(min(0.20, prob), 4)


def _path_viability_from_teammates(teammate_scores: list[float]) -> float:
    """Map average teammate impact (BPM-like units) to a [0.5, 1.5] multiplier.

    Anchors:
      avg <= -1.0  -> 0.5  (championship path effectively closed)
      avg ==  0.0  -> 1.0  (league-average support)
      avg >= +2.0  -> 1.5  (elite co-stars)
    """
    if not teammate_scores:
        return 1.0
    avg = sum(teammate_scores) / len(teammate_scores)
    if avg <= -1.0:
        return 0.5
    if avg >= 2.0:
        return 1.5
    if avg < 0.0:
        # Linear from (avg=-1, mult=0.5) to (avg=0, mult=1.0)
        return 0.5 + (avg - (-1.0)) * 0.5
    # Linear from (avg=0, mult=1.0) to (avg=2, mult=1.5)
    return 1.0 + (avg / 2.0) * 0.5


def _bucket_shot_zone(zone: str) -> str | None:
    """Classify an NBA API zone string into RIM / MIDRANGE / THREE."""
    if not zone:
        return None
    z = zone.strip()
    if z in ("Restricted Area", "In The Paint (Non-RA)"):
        return "RIM"
    if z == "Mid-Range":
        return "MIDRANGE"
    if "3" in z or "Corner" in z:
        return "THREE"
    return None


def compute_playoff_ts_drop(
    advanced: Any,
    play_types: Any,
    shot_zones: list[Any] | None,
) -> float:
    """Compute expected regular-season -> playoff TS% drop (in TS% points).

    Uses a shot-mix-weighted model when ``shot_zones`` is available,
    splitting 3PT attempts between self-created and spot-up using
    play-type frequencies. Falls back to the legacy usage-tier heuristic
    when shot-zone data is missing or empty.
    """
    if shot_zones:
        iso_freq = safe_float(getattr(play_types, "isolation_freq", None))
        pnr_freq = safe_float(
            getattr(play_types, "pnr_ball_handler_freq", None)
        )
        post_freq = safe_float(getattr(play_types, "post_up_freq", None))
        spot_up_freq = safe_float(getattr(play_types, "spot_up_freq", None))
        handoff_freq = safe_float(getattr(play_types, "handoff_freq", None))
        cut_freq = safe_float(getattr(play_types, "cut_freq", None))

        self_creation = max(0.0, min(1.0, iso_freq + pnr_freq + post_freq))
        # Spot-up share intentionally excludes off-screen because that
        # action is ambiguously self-generated and league-wide samples
        # are too small to assign cleanly.
        spot_up_share = max(
            0.0, min(1.0, spot_up_freq + handoff_freq + cut_freq)
        )

        denom = self_creation + spot_up_share
        if denom > 0:
            self_created_three_share = self_creation / denom
        else:
            self_created_three_share = 0.5
        spot_up_three_share = 1.0 - self_created_three_share

        weighted_drop = 0.0
        total_freq = 0.0
        for sz in shot_zones:
            zone = getattr(sz, "zone", None) or ""
            bucket = _bucket_shot_zone(zone)
            if bucket is None:
                continue
            freq = safe_float(getattr(sz, "freq", None))
            if freq <= 0:
                continue
            total_freq += freq
            if bucket == "RIM":
                weighted_drop += freq * RIM_PLAYOFF_TS_DROP
            elif bucket == "MIDRANGE":
                weighted_drop += freq * MIDRANGE_PLAYOFF_TS_DROP
            else:  # THREE
                blended = (
                    self_created_three_share
                    * THREE_SELF_CREATED_PLAYOFF_TS_DROP
                    + spot_up_three_share
                    * THREE_SPOT_UP_PLAYOFF_TS_DROP
                )
                weighted_drop += freq * blended

        if total_freq > 0:
            return weighted_drop / total_freq

    # fallback: legacy usage-tier heuristic when shot-zone data is missing.
    usg = safe_float(getattr(advanced, "usg_pct", None), 0.20)
    if usg >= 0.28:
        return 0.010
    if usg >= 0.22:
        return 0.018
    return 0.028


class ChampionshipCalculator:
    """Computes the Championship Index from player data."""

    def __init__(
        self,
        season_stats: Any,
        advanced: Any,
        play_types: Any,
        clutch_stats: Any,
        on_off: Any,
        computed_advanced: Any,
        all_in_one: Any = None,
        career_stats: list | None = None,
        portability_score: float = 50.0,
        teammate_impact_scores: list[float] | None = None,
        shot_zones: list[Any] | None = None,
    ):
        """Initialize with player data.

        Args:
            season_stats: SeasonStats model
            advanced: PlayerAdvancedStats model
            play_types: SeasonPlayTypeStats model
            clutch_stats: PlayerClutchStats model
            on_off: PlayerOnOffStats model
            computed_advanced: PlayerComputedAdvanced model
            all_in_one: PlayerAllInOneMetrics model (optional)
            career_stats: List of PlayerCareerStats for trajectory (optional)
            portability_score: Pre-computed portability index (0-100)
            teammate_impact_scores: List of teammate BPM/EPM values (optional)
            shot_zones: List of PlayerShotZones rows for shot-diet modeling
                (optional; falls back to usage heuristic when absent)
        """
        self.ss = season_stats
        self.adv = advanced
        self.pt = play_types
        self.clutch = clutch_stats
        self.oo = on_off
        self.comp = computed_advanced
        self.aio = all_in_one
        self.career = career_stats or []
        self.portability_score = portability_score
        self.teammate_scores = teammate_impact_scores or []
        self.shot_zones = shot_zones or []

    # ----------------------------------------------------------------
    # Pillar 1: Playoff Scoring Projection (27%)
    # ----------------------------------------------------------------

    def _playoff_scoring(self) -> float:
        gp = max(1, self.ss.games_played or 1) if self.ss else 1
        ppg = safe_div(safe_float(self.ss.total_points), gp) if self.ss else 0

        usg = safe_float(self.adv.usg_pct, 0.20) if self.adv else 0.20
        ts = safe_float(self.adv.ts_pct, 0.55) if self.adv else 0.55

        ts_drop = compute_playoff_ts_drop(self.adv, self.pt, self.shot_zones)
        projected_ts = ts - ts_drop

        # Stars see usage bump in playoffs
        projected_usg = usg + (0.02 if usg >= 0.25 else 0)

        # Project PPG
        projected_ppg = (
            ppg
            * safe_div(projected_usg, usg)
            * safe_div(projected_ts, ts)
        )

        # Score components
        ts_score = normalize_to_0_100(projected_ts, min_val=0.50, max_val=0.65)
        ppg_score = normalize_to_0_100(projected_ppg, min_val=8, max_val=32)

        # Resilience: low catch-and-shoot dependency + high FT rate
        spot_up_freq = safe_float(self.pt.spot_up_freq) if self.pt else 0
        fta = safe_float(self.ss.total_fta) if self.ss else 0
        fga = safe_float(self.ss.total_fga, 1) if self.ss else 1
        ft_rate = safe_div(fta, fga)

        resilience = (1 - spot_up_freq) * 50 + min(50, ft_rate * 200)

        return ts_score * 0.35 + ppg_score * 0.40 + resilience * 0.25

    # ----------------------------------------------------------------
    # Pillar 2: Two-Way Impact (23%)
    # ----------------------------------------------------------------

    def _two_way_impact(self) -> float:
        if self.aio:
            off_metrics = [
                safe_float(m)
                for m in [
                    self.aio.epm_offense, self.aio.rpm_offense,
                    self.aio.lebron_offense, self.aio.darko_offense,
                ]
                if m is not None
            ]
            def_metrics = [
                safe_float(m)
                for m in [
                    self.aio.epm_defense, self.aio.rpm_defense,
                    self.aio.lebron_defense, self.aio.darko_defense,
                ]
                if m is not None
            ]

            avg_off = sum(off_metrics) / len(off_metrics) if off_metrics else 0
            avg_def = sum(def_metrics) / len(def_metrics) if def_metrics else 0

            off_score = normalize_to_0_100(avg_off, min_val=-3, max_val=5)
            def_score = normalize_to_0_100(avg_def, min_val=-3, max_val=3)

            two_way_bonus = 10 if avg_off > 0 and avg_def > 0 else 0

            return min(100, off_score * 0.55 + def_score * 0.45 + two_way_bonus)

        if self.comp:
            obpm = safe_float(self.comp.obpm)
            dbpm = safe_float(self.comp.dbpm)
            off_score = normalize_to_0_100(obpm, min_val=-3, max_val=6)
            def_score = normalize_to_0_100(dbpm, min_val=-3, max_val=4)
            two_way_bonus = 10 if obpm > 0 and dbpm > 0 else 0
            return min(100, off_score * 0.55 + def_score * 0.45 + two_way_bonus)

        return 50.0

    # ----------------------------------------------------------------
    # Pillar 3: Clutch & Pressure Performance (15%)
    # ----------------------------------------------------------------

    def _clutch_performance(self) -> float:
        if not self.clutch:
            return 50.0

        gp = self.clutch.games_played or 0
        if gp == 0:
            return 50.0

        clutch_pts = safe_float(self.clutch.pts)
        clutch_fga = safe_float(self.clutch.fga)
        clutch_fta = safe_float(self.clutch.fta)

        # Aggregate clutch totals (per-game * gp)
        total_fga = clutch_fga * gp
        total_fta = clutch_fta * gp
        total_pts = clutch_pts * gp
        observed_tsa = total_fga + 0.44 * total_fta

        raw_clutch_ts = (
            safe_div(total_pts, 2 * observed_tsa)
            if observed_tsa > 0
            else 0.50
        )

        # Bayesian shrinkage toward the player's regular-season TS%.
        # Prior strength is in TSA-equivalent units, so a 50-80 TSA
        # clutch sample is dominated by the prior, reflecting how noisy
        # raw clutch splits actually are year-over-year.
        prior_mean = (
            safe_float(self.adv.ts_pct, 0.55) if self.adv else 0.55
        )
        posterior_ts = (
            CLUTCH_PRIOR_STRENGTH * prior_mean
            + observed_tsa * raw_clutch_ts
        ) / (CLUTCH_PRIOR_STRENGTH + observed_tsa)

        ts_score = normalize_to_0_100(posterior_ts, min_val=0.45, max_val=0.65)

        clutch_net = safe_float(self.clutch.net_rating)
        net_score = normalize_to_0_100(clutch_net, min_val=-15, max_val=15)

        clutch_ppg = clutch_pts  # Already per-game in the source row
        volume_score = normalize_to_0_100(clutch_ppg, min_val=0.5, max_val=5)

        return ts_score * 0.40 + net_score * 0.35 + volume_score * 0.25

    # ----------------------------------------------------------------
    # Pillar 4: Portability (15%) — uses pre-computed score
    # ----------------------------------------------------------------

    def _portability(self) -> float:
        return self.portability_score

    # ----------------------------------------------------------------
    # Pillar 5: Durability & Availability (10%)
    # ----------------------------------------------------------------

    def _durability(self) -> float:
        if not self.ss:
            return 50.0

        gp = self.ss.games_played or 0
        gp_ratio = safe_div(gp, 82)
        gp_score = normalize_to_0_100(gp_ratio, min_val=0.50, max_val=1.0)

        total_min = safe_float(self.ss.total_minutes)
        mpg = safe_div(total_min, max(1, gp))
        if mpg >= 30:
            minutes_score = normalize_to_0_100(mpg, min_val=28, max_val=38)
        else:
            minutes_score = normalize_to_0_100(mpg, min_val=15, max_val=32)

        return gp_score * 0.70 + minutes_score * 0.30

    # ----------------------------------------------------------------
    # Pillar 6: Playoff Experience & Growth Arc (10%)
    # ----------------------------------------------------------------

    def _experience_arc(self) -> float:
        if not self.career:
            return 40.0

        seasons = sorted(
            self.career,
            key=lambda c: c.season if hasattr(c, "season") else "",
        )

        num_seasons = len(seasons)
        experience_score = normalize_to_0_100(num_seasons, min_val=0, max_val=10)

        if len(seasons) >= 2 and self.comp:
            current_bpm = safe_float(self.comp.bpm)
            trajectory_score = normalize_to_0_100(
                current_bpm, min_val=-2, max_val=6
            )
        else:
            trajectory_score = 50.0

        playoff_bonus = (
            min(20, num_seasons * 3) if num_seasons >= 3 else 0
        )

        return min(
            100,
            experience_score * 0.40 + trajectory_score * 0.40 + playoff_bonus,
        )

    # ----------------------------------------------------------------
    # Path Viability (post-index multiplier on win probability)
    # ----------------------------------------------------------------

    def _path_viability(self) -> float:
        return _path_viability_from_teammates(self.teammate_scores)

    # ----------------------------------------------------------------
    # Full Calculation
    # ----------------------------------------------------------------

    def calculate(self) -> ChampionshipResult:
        """Calculate the complete Championship Index."""
        return ChampionshipResult(
            playoff_scoring=round(self._playoff_scoring(), 1),
            two_way_impact=round(self._two_way_impact(), 1),
            clutch_performance=round(self._clutch_performance(), 1),
            portability=round(self._portability(), 1),
            durability=round(self._durability(), 1),
            experience_arc=round(self._experience_arc(), 1),
            path_viability=round(self._path_viability(), 3),
        )
