"""Service for calculating contextualized impact ratings.

This module implements a simplified RAPM-lite approach that adjusts
raw on/off data by accounting for:
- Teammate quality (playing with stars inflates stats)
- Opponent quality (starters vs bench)
- Minutes reliability (more minutes = more stable signal)
"""

from dataclasses import dataclass
from decimal import Decimal

from app.services.nba_data import LineupData, PlayerOnOffData


# Constants for impact calculation
LEAGUE_AVG_NET_RATING = Decimal("0.0")  # League average net rating is ~0
MIN_MINUTES_THRESHOLD = Decimal("100")  # Minimum minutes for reliable impact
FULL_RELIABILITY_MINUTES = Decimal("1000")  # Minutes for full reliability weight

# Opponent quality multipliers
STARTER_MINUTES_MULTIPLIER = Decimal("1.2")  # Impact vs starters weighted higher
BENCH_MINUTES_MULTIPLIER = Decimal("0.8")  # Impact vs bench weighted lower


@dataclass
class ContextualizedImpactData:
    """Calculated contextualized impact for a player."""

    player_id: int
    player_name: str

    # Raw on/off differential
    raw_net_rating_diff: Decimal
    raw_off_rating_diff: Decimal
    raw_def_rating_diff: Decimal

    # Teammate context
    avg_teammate_net_rating: Decimal
    teammate_adjustment: Decimal

    # Opponent quality context
    pct_minutes_vs_starters: Decimal
    opponent_quality_factor: Decimal

    # Reliability
    total_on_court_minutes: Decimal
    reliability_factor: Decimal

    # Final contextualized metrics
    contextualized_off_impact: Decimal
    contextualized_def_impact: Decimal
    contextualized_net_impact: Decimal


class ImpactCalculator:
    """Calculator for contextualized impact ratings.

    The contextualized impact formula:

    contextualized_impact = (
        raw_net_rating_diff
        - teammate_adjustment
    ) * opponent_quality_factor * reliability_factor

    Where:
    - teammate_adjustment = avg_teammate_net_rating - league_avg
    - opponent_quality_factor = weighted average based on starter/bench minutes
    - reliability_factor = min(1.0, sqrt(minutes / FULL_RELIABILITY_MINUTES))
    """

    def __init__(
        self,
        lineup_data: list[LineupData],
        on_off_data: dict[int, PlayerOnOffData],
    ):
        """Initialize calculator with lineup and on/off data.

        Args:
            lineup_data: List of 5-man lineup data
            on_off_data: Dict of player on/off data keyed by player_id
        """
        self.lineup_data = lineup_data
        self.on_off_data = on_off_data

        # Pre-compute player net ratings for teammate calculations
        self._player_net_ratings: dict[int, Decimal] = {}
        for player_id, data in on_off_data.items():
            self._player_net_ratings[player_id] = data.on_court_net_rating

        # Compute league average net rating from all players
        if self._player_net_ratings:
            total = sum(self._player_net_ratings.values())
            self._league_avg_net_rating = total / Decimal(len(self._player_net_ratings))
        else:
            self._league_avg_net_rating = LEAGUE_AVG_NET_RATING

        # Build teammate lookup from lineup data
        self._teammate_minutes = self._build_teammate_minutes()

    def _build_teammate_minutes(self) -> dict[int, dict[int, Decimal]]:
        """Build a lookup of minutes played with each teammate.

        Returns:
            Dict mapping player_id -> {teammate_id -> shared_minutes}
        """
        teammate_minutes: dict[int, dict[int, Decimal]] = {}

        for lineup in self.lineup_data:
            lineup_minutes = lineup.minutes
            player_ids = lineup.player_ids

            for player_id in player_ids:
                if player_id not in teammate_minutes:
                    teammate_minutes[player_id] = {}

                for teammate_id in player_ids:
                    if teammate_id != player_id:
                        if teammate_id not in teammate_minutes[player_id]:
                            teammate_minutes[player_id][teammate_id] = Decimal("0")
                        teammate_minutes[player_id][teammate_id] += lineup_minutes

        return teammate_minutes

    def _calculate_avg_teammate_rating(self, player_id: int) -> Decimal:
        """Calculate weighted average net rating of teammates.

        Args:
            player_id: The player to calculate teammate rating for

        Returns:
            Minutes-weighted average teammate net rating
        """
        if player_id not in self._teammate_minutes:
            return self._league_avg_net_rating

        teammate_data = self._teammate_minutes[player_id]
        total_weighted_rating = Decimal("0")
        total_minutes = Decimal("0")

        for teammate_id, shared_minutes in teammate_data.items():
            teammate_rating = self._player_net_ratings.get(
                teammate_id, self._league_avg_net_rating
            )
            total_weighted_rating += teammate_rating * shared_minutes
            total_minutes += shared_minutes

        if total_minutes > 0:
            return total_weighted_rating / total_minutes
        return self._league_avg_net_rating

    def _calculate_reliability_factor(self, minutes: Decimal) -> Decimal:
        """Calculate reliability factor based on minutes played.

        More minutes = more reliable signal.
        Uses square root scaling for diminishing returns.

        Args:
            minutes: Total on-court minutes

        Returns:
            Reliability factor between 0 and 1
        """
        if minutes < MIN_MINUTES_THRESHOLD:
            return Decimal("0")

        # Square root scaling with cap at 1.0
        ratio = minutes / FULL_RELIABILITY_MINUTES
        factor = ratio.sqrt() if hasattr(ratio, "sqrt") else Decimal(str(float(ratio) ** 0.5))
        return min(Decimal("1.0"), factor)

    def _estimate_opponent_quality_factor(self, player_id: int) -> tuple[Decimal, Decimal]:
        """Estimate opponent quality factor.

        Without detailed matchup data, we estimate based on minutes distribution.
        Players with more minutes likely faced more starters.

        Args:
            player_id: Player to estimate for

        Returns:
            Tuple of (pct_vs_starters, quality_factor)
        """
        on_off = self.on_off_data.get(player_id)
        if not on_off:
            return Decimal("0.5"), Decimal("1.0")

        total_minutes = on_off.on_court_min

        # Estimate: Players with more minutes faced proportionally more starters
        # This is a simplification - real RAPM would use actual matchup data
        if total_minutes > Decimal("1500"):
            pct_starters = Decimal("0.70")
        elif total_minutes > Decimal("1000"):
            pct_starters = Decimal("0.60")
        elif total_minutes > Decimal("500"):
            pct_starters = Decimal("0.50")
        else:
            pct_starters = Decimal("0.40")

        # Calculate weighted quality factor
        pct_bench = Decimal("1.0") - pct_starters
        quality_factor = (
            pct_starters * STARTER_MINUTES_MULTIPLIER
            + pct_bench * BENCH_MINUTES_MULTIPLIER
        )

        return pct_starters, quality_factor

    def calculate_impact(self, player_id: int) -> ContextualizedImpactData | None:
        """Calculate contextualized impact for a single player.

        Args:
            player_id: Player to calculate impact for

        Returns:
            ContextualizedImpactData or None if insufficient data
        """
        on_off = self.on_off_data.get(player_id)
        if not on_off:
            return None

        # Raw differentials
        raw_net_diff = on_off.net_rating_diff
        raw_off_diff = on_off.off_rating_diff
        raw_def_diff = on_off.def_rating_diff

        # Teammate adjustment
        avg_teammate_rating = self._calculate_avg_teammate_rating(player_id)
        teammate_adjustment = avg_teammate_rating - self._league_avg_net_rating

        # Opponent quality
        pct_starters, opponent_factor = self._estimate_opponent_quality_factor(player_id)

        # Reliability
        total_minutes = on_off.on_court_min
        reliability = self._calculate_reliability_factor(total_minutes)

        # Skip players with insufficient minutes
        if reliability == 0:
            return None

        # Calculate contextualized impact
        # Adjust raw diff by teammate context, then scale by opponent quality and reliability
        adjusted_net = raw_net_diff - teammate_adjustment
        adjusted_off = raw_off_diff - (teammate_adjustment * Decimal("0.6"))  # Offense more teammate-dependent
        adjusted_def = raw_def_diff - (teammate_adjustment * Decimal("0.4"))  # Defense less teammate-dependent

        contextualized_net = (adjusted_net * opponent_factor * reliability).quantize(Decimal("0.01"))
        contextualized_off = (adjusted_off * opponent_factor * reliability).quantize(Decimal("0.01"))
        contextualized_def = (adjusted_def * opponent_factor * reliability).quantize(Decimal("0.01"))

        return ContextualizedImpactData(
            player_id=player_id,
            player_name=on_off.player_name,
            raw_net_rating_diff=raw_net_diff,
            raw_off_rating_diff=raw_off_diff,
            raw_def_rating_diff=raw_def_diff,
            avg_teammate_net_rating=avg_teammate_rating.quantize(Decimal("0.01")),
            teammate_adjustment=teammate_adjustment.quantize(Decimal("0.01")),
            pct_minutes_vs_starters=pct_starters,
            opponent_quality_factor=opponent_factor.quantize(Decimal("0.001")),
            total_on_court_minutes=total_minutes,
            reliability_factor=reliability.quantize(Decimal("0.001")),
            contextualized_off_impact=contextualized_off,
            contextualized_def_impact=contextualized_def,
            contextualized_net_impact=contextualized_net,
        )

    def calculate_all_impacts(self) -> dict[int, ContextualizedImpactData]:
        """Calculate contextualized impact for all players.

        Returns:
            Dict mapping player_id to ContextualizedImpactData
        """
        impacts: dict[int, ContextualizedImpactData] = {}

        for player_id in self.on_off_data.keys():
            impact = self.calculate_impact(player_id)
            if impact is not None:
                impacts[player_id] = impact

        return impacts
