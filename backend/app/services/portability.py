"""Portability Index service.

Evaluates how well a player's production transfers across team contexts.
Produces a 0-100 composite score from four sub-scores:
- Self-Creation (30%): Independent offensive generation ability
- Scheme Flexibility (25%): Fit across multiple offensive archetypes
- Defensive Switchability (25%): Ability to guard multiple positions
- Low Dependency (20%): Performance stability regardless of teammates
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field

from app.services.metrics_utils import (
    POSITION_LEAGUE_AVG_FG,
    map_position_to_bucket,
    normalize_to_0_100,
    percentile_rank,
    safe_div,
    safe_float,
)

logger = logging.getLogger(__name__)

# Sub-score weights in the final Portability Index
SELF_CREATION_WEIGHT = 0.30
SCHEME_FLEXIBILITY_WEIGHT = 0.25
SWITCHABILITY_WEIGHT = 0.25
LOW_DEPENDENCY_WEIGHT = 0.20

# Minimum thresholds
MIN_SELF_CREATED_POSS = 50
MIN_MATCHUP_POSS = 10
MIN_MATCHUP_FGA_PER_BUCKET = 20
MIN_LINEUP_MINUTES = 20


@dataclass
class PortabilityResult:
    """Complete portability analysis for a player."""

    # Sub-scores (0-100)
    self_creation: float = 50.0
    scheme_flexibility: float = 50.0
    switchability: float = 50.0
    low_dependency: float = 50.0

    # Self-creation sub-components
    unassisted_rate_score: float = 50.0
    self_created_ppp_score: float = 50.0
    gravity_score: float = 50.0
    creation_volume_score: float = 50.0

    # Switchability details
    positions_guarded: dict = field(default_factory=dict)

    # Final composite
    portability_index: float = 50.0
    grade: str = "C"

    def __post_init__(self):
        self.portability_index = (
            self.self_creation * SELF_CREATION_WEIGHT
            + self.scheme_flexibility * SCHEME_FLEXIBILITY_WEIGHT
            + self.switchability * SWITCHABILITY_WEIGHT
            + self.low_dependency * LOW_DEPENDENCY_WEIGHT
        )
        self.grade = _score_to_grade(self.portability_index)


def _score_to_grade(score: float) -> str:
    """Convert a 0-100 score to a letter grade."""
    if score >= 90:
        return "A+"
    elif score >= 85:
        return "A"
    elif score >= 80:
        return "A-"
    elif score >= 75:
        return "B+"
    elif score >= 70:
        return "B"
    elif score >= 65:
        return "B-"
    elif score >= 60:
        return "C+"
    elif score >= 55:
        return "C"
    elif score >= 50:
        return "C-"
    elif score >= 45:
        return "D+"
    elif score >= 40:
        return "D"
    else:
        return "F"


class PortabilityCalculator:
    """Computes the Portability Index and its sub-scores."""

    def __init__(
        self,
        season_stats,
        play_types,
        shooting_tracking,
        advanced,
        on_off,
        per75,
        matchups: list | None = None,
        all_players_positions: dict[int, str] | None = None,
        league_distributions: dict | None = None,
        scheme_scores: dict | None = None,
    ):
        """Initialize with player data objects.

        Args:
            season_stats: SeasonStats model instance
            play_types: SeasonPlayTypeStats model instance
            shooting_tracking: PlayerShootingTracking model instance
            advanced: PlayerAdvancedStats model instance
            on_off: PlayerOnOffStats model instance
            per75: Per75Stats model instance
            matchups: List of PlayerMatchups for defensive switchability
            all_players_positions: Dict mapping off_player_nba_id -> position string
            league_distributions: Dict of stat name -> list of all player values
                for percentile computation (optional, uses raw normalization if absent)
            scheme_scores: Pre-computed scheme compatibility scores dict
                from SchemeCompatibilityCalculator (optional)
        """
        self.ss = season_stats
        self.pt = play_types
        self.st = shooting_tracking
        self.adv = advanced
        self.oo = on_off
        self.p75 = per75
        self.matchups = matchups or []
        self.positions = all_players_positions or {}
        self.league = league_distributions or {}
        self.scheme_scores = scheme_scores

    def _pctile(self, value: float, stat_key: str) -> float:
        """Compute percentile if league distribution available, else normalize."""
        dist = self.league.get(stat_key)
        if dist:
            return percentile_rank(value, dist)
        return 50.0

    # ----------------------------------------------------------------
    # Self-Creation Score
    # ----------------------------------------------------------------

    def _unassisted_rate_score(self) -> float:
        """Score based on percentage of FGA that are self-created."""
        gp = max(1, self.ss.games_played or 1)

        # Approximate unassisted FGA from pull-up + ISO + drives
        pullup_fga_total = safe_float(self.st.pullup_fga) * gp if self.st else 0
        iso_fga = safe_float(self.pt.isolation_fga) if self.pt else 0
        drive_fga_total = safe_float(self.st.drive_fga) * gp if self.st else 0

        unassisted_fga = pullup_fga_total + iso_fga + drive_fga_total
        total_fga = safe_float(self.ss.total_fga, 1)

        pct_unassisted = safe_div(unassisted_fga, total_fga)

        # League avg ~0.35, elite ~0.55-0.65, catch-and-shoot ~0.10-0.20
        return self._pctile(pct_unassisted, "pct_unassisted")

    def _self_created_ppp_score(self) -> float:
        """Score based on efficiency on self-created possessions."""
        iso_poss = safe_float(self.pt.isolation_poss) if self.pt else 0
        pnr_poss = safe_float(self.pt.pnr_ball_handler_poss) if self.pt else 0
        iso_pts = safe_float(self.pt.isolation_pts) if self.pt else 0
        pnr_pts = safe_float(self.pt.pnr_ball_handler_pts) if self.pt else 0

        total_poss = iso_poss + pnr_poss
        total_pts = iso_pts + pnr_pts

        if total_poss < MIN_SELF_CREATED_POSS:
            return 40.0  # Cap for low volume

        ppp = safe_div(total_pts, total_poss)
        # League avg self-created PPP ~0.85-0.90, elite 1.00+
        return normalize_to_0_100(ppp, min_val=0.70, max_val=1.10)

    def _gravity_score(self) -> float:
        """Proxy for off-ball gravity using available data."""
        # Component 1: Team offensive lift when on court
        off_rating_lift = safe_float(self.oo.off_rating_diff) if self.oo else 0
        lift_score = normalize_to_0_100(off_rating_lift, min_val=-5, max_val=5)

        # Component 2: Shot creation for teammates (AST ratio + screen assists)
        ast_ratio = safe_float(self.adv.ast_ratio) if self.adv else 0
        creation_score = normalize_to_0_100(ast_ratio, min_val=5, max_val=30)

        # Component 3: Pull-up 3PT volume (draws closeouts)
        pullup_3pa = safe_float(self.st.pullup_fg3a) if self.st else 0
        pullup_3_score = normalize_to_0_100(pullup_3pa, min_val=0, max_val=6)

        # Component 4: Points per touch efficiency
        ppt = safe_float(self.ss.avg_points_per_touch) if self.ss else 0
        ppt_score = normalize_to_0_100(ppt, min_val=0.2, max_val=0.7)

        return (
            lift_score * 0.30
            + creation_score * 0.30
            + pullup_3_score * 0.20
            + ppt_score * 0.20
        )

    def _creation_volume_score(self) -> float:
        """Score based on what fraction of possessions are self-created."""
        iso_freq = safe_float(self.pt.isolation_freq) if self.pt else 0
        pnr_freq = safe_float(self.pt.pnr_ball_handler_freq) if self.pt else 0

        creation_freq = iso_freq + pnr_freq
        # League avg ~0.25-0.30, elite guards 0.45-0.55
        return normalize_to_0_100(creation_freq, min_val=0.05, max_val=0.55)

    def calculate_self_creation(self) -> float:
        """Calculate the Self-Creation sub-score (0-100)."""
        return (
            self._unassisted_rate_score() * 0.25
            + self._self_created_ppp_score() * 0.25
            + self._gravity_score() * 0.25
            + self._creation_volume_score() * 0.25
        )

    # ----------------------------------------------------------------
    # Defensive Switchability Score
    # ----------------------------------------------------------------

    def calculate_switchability(self) -> tuple[float, dict]:
        """Calculate defensive switchability from matchup data.

        Returns:
            Tuple of (score 0-100, position_scores dict)
        """
        if not self.matchups:
            return 50.0, {}

        # Group matchups by opponent position bucket
        position_stats: dict[str, dict] = {
            "G": {"fgm": 0.0, "fga": 0.0, "poss": 0.0},
            "W": {"fgm": 0.0, "fga": 0.0, "poss": 0.0},
            "F": {"fgm": 0.0, "fga": 0.0, "poss": 0.0},
            "C": {"fgm": 0.0, "fga": 0.0, "poss": 0.0},
        }

        for m in self.matchups:
            poss = safe_float(m.partial_poss)
            if poss < MIN_MATCHUP_POSS:
                continue

            opp_pos = self.positions.get(m.off_player_nba_id, "")
            bucket = map_position_to_bucket(opp_pos)

            position_stats[bucket]["fgm"] += safe_float(m.matchup_fgm)
            position_stats[bucket]["fga"] += safe_float(m.matchup_fga)
            position_stats[bucket]["poss"] += poss

        # Score each position
        position_scores = {}
        for pos, stats in position_stats.items():
            if stats["fga"] < MIN_MATCHUP_FGA_PER_BUCKET:
                position_scores[pos] = None
                continue

            matchup_fg_pct = safe_div(stats["fgm"], stats["fga"])
            league_avg = POSITION_LEAGUE_AVG_FG[pos]
            diff = matchup_fg_pct - league_avg

            # Each 1% below league avg = +5 points, above = -5 points
            pos_score = max(0.0, min(100.0, 50 - (diff * 500)))
            position_scores[pos] = round(pos_score, 1)

        valid_scores = [v for v in position_scores.values() if v is not None]
        if not valid_scores:
            return 50.0, position_scores

        avg_score = sum(valid_scores) / len(valid_scores)
        positions_above_50 = sum(1 for s in valid_scores if s >= 50)
        breadth_bonus = (positions_above_50 / 4) * 20

        switchability = min(100.0, avg_score + breadth_bonus)
        return round(switchability, 1), position_scores

    # ----------------------------------------------------------------
    # Low Dependency Score
    # ----------------------------------------------------------------

    def calculate_low_dependency(self) -> float:
        """Estimate teammate dependency from on/off data.

        Without granular lineup bucketing, we use on/off variance as a proxy.
        High on/off differential suggests the player elevates any lineup,
        while low or negative suggests dependency on specific teammates.
        """
        if not self.oo:
            return 50.0

        # On/off net rating diff: positive means player helps any lineup
        net_diff = safe_float(self.oo.net_rating_diff)

        # Off-court net rating: if team is bad without you, you're less dependent
        off_court_net = safe_float(self.oo.off_court_net_rating)

        # Component 1: On/off impact (higher = more independent value)
        impact_score = normalize_to_0_100(net_diff, min_val=-5, max_val=10)

        # Component 2: Performance without star context
        # If off-court team is bad but on-court is good -> player is the engine
        off_court_penalty = normalize_to_0_100(off_court_net, min_val=-10, max_val=5)
        # Invert: worse off-court = player is more self-sufficient
        self_sufficiency = 100 - off_court_penalty

        # Component 3: Usage efficiency balance
        # High usage + high efficiency = can carry load independently
        usg = safe_float(self.adv.usg_pct) if self.adv else 0.20
        ts = safe_float(self.adv.ts_pct) if self.adv else 0.55
        # USG > 25% and TS > 57% = elite independent creator
        usg_score = normalize_to_0_100(usg, min_val=0.15, max_val=0.32)
        ts_score = normalize_to_0_100(ts, min_val=0.50, max_val=0.65)
        efficiency_load = (usg_score + ts_score) / 2

        return (
            impact_score * 0.40
            + self_sufficiency * 0.30
            + efficiency_load * 0.30
        )

    # ----------------------------------------------------------------
    # Full Calculation
    # ----------------------------------------------------------------

    def calculate(self) -> PortabilityResult:
        """Calculate the complete Portability Index."""
        # Self-Creation
        unassisted = self._unassisted_rate_score()
        self_ppp = self._self_created_ppp_score()
        gravity = self._gravity_score()
        volume = self._creation_volume_score()
        self_creation = unassisted * 0.25 + self_ppp * 0.25 + gravity * 0.25 + volume * 0.25

        # Scheme Flexibility (from pre-computed scheme scores or default)
        if self.scheme_scores:
            scheme_flexibility = self.scheme_scores.get("scheme_flexibility", 50.0)
        else:
            scheme_flexibility = 50.0

        # Defensive Switchability
        switchability, position_scores = self.calculate_switchability()

        # Low Dependency
        low_dependency = self.calculate_low_dependency()

        result = PortabilityResult(
            self_creation=round(self_creation, 1),
            scheme_flexibility=round(scheme_flexibility, 1),
            switchability=round(switchability, 1),
            low_dependency=round(low_dependency, 1),
            unassisted_rate_score=round(unassisted, 1),
            self_created_ppp_score=round(self_ppp, 1),
            gravity_score=round(gravity, 1),
            creation_volume_score=round(volume, 1),
            positions_guarded=position_scores,
        )
        return result
