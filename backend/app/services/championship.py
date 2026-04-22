"""Championship Index service.

Computes a 0-100 composite score evaluating whether a player can lead
a team to a championship as the #1 option. Synthesizes seven weighted
pillars derived from available stats.

Pillars and weights:
1. Playoff Scoring Projection (25%)
2. Two-Way Impact (20%)
3. Clutch & Pressure Performance (15%)
4. Portability / Roster Flexibility (15%)
5. Durability & Availability (10%)
6. Playoff Experience & Growth Arc (10%)
7. Supporting Cast Threshold (5%)
"""

from __future__ import annotations

import logging
from dataclasses import dataclass

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
    supporting_cast: float = 50.0

    # Final composite
    championship_index: float = 50.0
    tier: str = "CHAMPIONSHIP PIECE"
    win_probability: float = 0.033
    multiplier_vs_base: float = 1.0

    def __post_init__(self):
        self.championship_index = round(
            self.playoff_scoring * 0.25
            + self.two_way_impact * 0.20
            + self.clutch_performance * 0.15
            + self.portability * 0.15
            + self.durability * 0.10
            + self.experience_arc * 0.10
            + self.supporting_cast * 0.05,
            1,
        )
        self.tier = _index_to_tier(self.championship_index)
        self.win_probability = _index_to_win_prob(self.championship_index)
        self.multiplier_vs_base = round(self.win_probability / HISTORICAL_BASE_RATE, 1)


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
    # Exponential mapping: base_rate * e^(k * (index - 50))
    import math

    k = 0.03  # Steepness factor
    prob = HISTORICAL_BASE_RATE * math.exp(k * (index - 50))
    return round(min(0.20, prob), 4)


class ChampionshipCalculator:
    """Computes the Championship Index from player data."""

    def __init__(
        self,
        season_stats,
        advanced,
        play_types,
        clutch_stats,
        on_off,
        computed_advanced,
        all_in_one=None,
        career_stats: list | None = None,
        portability_score: float = 50.0,
        teammate_impact_scores: list[float] | None = None,
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

    # ----------------------------------------------------------------
    # Pillar 1: Playoff Scoring Projection (25%)
    # ----------------------------------------------------------------

    def _playoff_scoring(self) -> float:
        gp = max(1, self.ss.games_played or 1) if self.ss else 1
        ppg = safe_div(safe_float(self.ss.total_points), gp) if self.ss else 0

        usg = safe_float(self.adv.usg_pct, 0.20) if self.adv else 0.20
        ts = safe_float(self.adv.ts_pct, 0.55) if self.adv else 0.55

        # Historical playoff TS% drop by usage tier
        if usg >= 0.28:
            ts_drop = 0.010
        elif usg >= 0.22:
            ts_drop = 0.018
        else:
            ts_drop = 0.028

        projected_ts = ts - ts_drop

        # Self-creation bonus: self-creators maintain better in playoffs
        iso_freq = safe_float(self.pt.isolation_freq) if self.pt else 0
        pnr_freq = safe_float(self.pt.pnr_ball_handler_freq) if self.pt else 0
        if iso_freq + pnr_freq > 0.40:
            projected_ts += 0.005

        # Stars see usage bump in playoffs
        projected_usg = usg + (0.02 if usg >= 0.25 else 0)

        # Project PPG
        projected_ppg = ppg * safe_div(projected_usg, usg) * safe_div(projected_ts, ts)

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
    # Pillar 2: Two-Way Impact (20%)
    # ----------------------------------------------------------------

    def _two_way_impact(self) -> float:
        if self.aio:
            # Average available offensive metrics
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

            # Scale: elite ~+4, average ~0, bad ~-3
            off_score = normalize_to_0_100(avg_off, min_val=-3, max_val=5)
            def_score = normalize_to_0_100(avg_def, min_val=-3, max_val=3)

            # Bonus for being positive on BOTH sides
            two_way_bonus = 10 if avg_off > 0 and avg_def > 0 else 0

            return min(100, off_score * 0.55 + def_score * 0.45 + two_way_bonus)

        # Fallback to BPM
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

        gp = max(1, self.clutch.games_played or 1)
        if gp < 10:
            return 50.0  # Insufficient sample

        clutch_pts = safe_float(self.clutch.pts)
        clutch_fga = safe_float(self.clutch.fga)
        clutch_fta = safe_float(self.clutch.fta)

        # Clutch TS%
        total_fga = clutch_fga * gp
        total_fta = clutch_fta * gp
        total_pts = clutch_pts * gp
        tsa = total_fga + 0.44 * total_fta

        clutch_ts = safe_div(total_pts, 2 * tsa) if tsa > 0 else 0.50
        ts_score = normalize_to_0_100(clutch_ts, min_val=0.45, max_val=0.65)

        # Clutch net rating
        clutch_net = safe_float(self.clutch.net_rating)
        net_score = normalize_to_0_100(clutch_net, min_val=-15, max_val=15)

        # Volume: clutch PPG
        clutch_ppg = clutch_pts  # Already per-game
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
        # 82-game season baseline
        gp_ratio = safe_div(gp, 82)
        gp_score = normalize_to_0_100(gp_ratio, min_val=0.50, max_val=1.0)

        # Minutes load: too many minutes = injury risk; too few = not a starter
        total_min = safe_float(self.ss.total_minutes)
        mpg = safe_div(total_min, max(1, gp))
        # Sweet spot: 30-36 mpg
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
            return 40.0  # Default for rookies / no data

        # Count seasons and check trajectory
        seasons = sorted(self.career, key=lambda c: c.season if hasattr(c, "season") else "")

        num_seasons = len(seasons)
        experience_score = normalize_to_0_100(num_seasons, min_val=0, max_val=10)

        # Growth trajectory: compare last 2 seasons of BPM/PER if available
        if len(seasons) >= 2 and self.comp:
            current_bpm = safe_float(self.comp.bpm)
            # Assume improvement if current BPM is positive
            trajectory_score = normalize_to_0_100(current_bpm, min_val=-2, max_val=6)
        else:
            trajectory_score = 50.0

        # Playoff games (rough estimate from career data)
        # Without explicit playoff flag, use season count as proxy
        playoff_bonus = min(20, num_seasons * 3) if num_seasons >= 3 else 0

        return min(100, experience_score * 0.40 + trajectory_score * 0.40 + playoff_bonus)

    # ----------------------------------------------------------------
    # Pillar 7: Supporting Cast Threshold (5%)
    # ----------------------------------------------------------------

    def _supporting_cast(self) -> float:
        """Evaluate current teammates using impact metrics.

        Higher score means the player already has good support (fewer
        upgrades needed to contend).
        """
        if not self.teammate_scores:
            return 50.0

        # Average teammate impact
        avg_teammate = sum(self.teammate_scores) / len(self.teammate_scores)

        # Best teammate
        best_teammate = max(self.teammate_scores) if self.teammate_scores else 0

        # Score: better teammates = easier path to championship
        avg_score = normalize_to_0_100(avg_teammate, min_val=-2, max_val=3)
        best_score = normalize_to_0_100(best_teammate, min_val=-1, max_val=5)

        return avg_score * 0.50 + best_score * 0.50

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
            supporting_cast=round(self._supporting_cast(), 1),
        )
