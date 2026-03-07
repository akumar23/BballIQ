"""Service for calculating offensive and defensive metrics."""

from decimal import Decimal

from app.core.config import settings


class MetricsCalculator:
    """
    Calculates per-touch offensive and defensive metrics.

    Offensive Metric Formula:
        (w1 * points_per_touch + w2 * assist_rate - w3 * turnover_rate) * volume_factor

    Defensive Metric Formula:
        (w1 * deflections_per_100 + w2 * contests_per_100 + w3 * steals_per_100) * volume_factor

    Volume Factor:
        (player_touches / league_avg_touches) ^ 0.5
    """

    # Offensive weights
    WEIGHT_POINTS_PER_TOUCH = Decimal("40")
    WEIGHT_ASSIST_RATE = Decimal("25")
    WEIGHT_TURNOVER_RATE = Decimal("-15")
    WEIGHT_FT_RATE = Decimal("10")

    # Defensive weights
    WEIGHT_DEFLECTIONS = Decimal("30")
    WEIGHT_CONTESTS = Decimal("25")
    WEIGHT_STEALS = Decimal("20")
    WEIGHT_CHARGES = Decimal("15")
    WEIGHT_LOOSE_BALLS = Decimal("10")

    # Volume scaling exponent (diminishing returns)
    VOLUME_EXPONENT = Decimal("0.5")

    def __init__(self, league_avg_touches: Decimal):
        self.league_avg_touches = league_avg_touches

    def calculate_volume_factor(self, player_touches: int) -> Decimal:
        """Calculate volume scaling factor."""
        if player_touches < settings.min_touches_for_metric:
            return Decimal("0")

        ratio = Decimal(player_touches) / self.league_avg_touches
        return ratio ** self.VOLUME_EXPONENT

    def calculate_offensive_metric(
        self,
        points_per_touch: Decimal,
        assist_rate: Decimal,
        turnover_rate: Decimal,
        ft_rate: Decimal,
        total_touches: int,
    ) -> Decimal:
        """Calculate single-number offensive metric."""
        volume_factor = self.calculate_volume_factor(total_touches)

        if volume_factor == 0:
            return Decimal("0")

        raw_metric = (
            self.WEIGHT_POINTS_PER_TOUCH * points_per_touch
            + self.WEIGHT_ASSIST_RATE * assist_rate
            + self.WEIGHT_TURNOVER_RATE * turnover_rate
            + self.WEIGHT_FT_RATE * ft_rate
        )

        return (raw_metric * volume_factor).quantize(Decimal("0.01"))

    def calculate_defensive_metric(
        self,
        deflections_per_100: Decimal,
        contests_per_100: Decimal,
        steals_per_100: Decimal,
        charges_per_100: Decimal,
        loose_balls_per_100: Decimal,
        total_possessions: int,
    ) -> Decimal:
        """Calculate single-number defensive metric."""
        # Use possessions as volume proxy for defense
        if total_possessions < 100:
            return Decimal("0")

        volume_factor = (Decimal(total_possessions) / Decimal("1000")) ** self.VOLUME_EXPONENT

        raw_metric = (
            self.WEIGHT_DEFLECTIONS * deflections_per_100
            + self.WEIGHT_CONTESTS * contests_per_100
            + self.WEIGHT_STEALS * steals_per_100
            + self.WEIGHT_CHARGES * charges_per_100
            + self.WEIGHT_LOOSE_BALLS * loose_balls_per_100
        )

        return (raw_metric * volume_factor).quantize(Decimal("0.01"))
