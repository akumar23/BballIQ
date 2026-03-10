"""Service for calculating per-75-possession stats.

Per 75 possessions normalizes player production to roughly one game's worth
of possessions (~75 per team per game), allowing fair comparison across
players with different minutes loads.
"""

from dataclasses import dataclass
from decimal import Decimal

# Standard possessions for normalization (roughly one game)
PER_75_BASE = Decimal("75")

# Minimum possessions required for meaningful per-75 stats
MIN_POSSESSIONS_THRESHOLD = 100


@dataclass
class Per75StatsData:
    """Container for per-75 possession stats."""

    # Scoring
    pts_per_75: Decimal
    fgm_per_75: Decimal
    fga_per_75: Decimal
    fg3m_per_75: Decimal
    fg3a_per_75: Decimal
    ftm_per_75: Decimal
    fta_per_75: Decimal

    # Playmaking
    ast_per_75: Decimal
    tov_per_75: Decimal

    # Rebounding
    reb_per_75: Decimal
    oreb_per_75: Decimal
    dreb_per_75: Decimal

    # Defense
    stl_per_75: Decimal
    blk_per_75: Decimal

    # Hustle stats
    deflections_per_75: Decimal
    contested_shots_per_75: Decimal
    contested_2pt_per_75: Decimal
    contested_3pt_per_75: Decimal
    charges_drawn_per_75: Decimal
    loose_balls_per_75: Decimal
    box_outs_per_75: Decimal
    screen_assists_per_75: Decimal

    # Ball handling
    touches_per_75: Decimal
    front_court_touches_per_75: Decimal

    # Reference
    possessions_used: int


class Per75Calculator:
    """Calculator for per-75-possession statistics.

    This calculator converts raw totals into per-75 possession rates,
    normalizing player production for comparison across different
    usage rates and minutes loads.
    """

    def __init__(self, possessions_per_minute: Decimal = Decimal("2.0")):
        """Initialize the calculator.

        Args:
            possessions_per_minute: Estimated possessions per minute played.
                                   NBA average is roughly 2.0 (100 poss per 48 min).
        """
        self.possessions_per_minute = possessions_per_minute

    def estimate_possessions(self, minutes: Decimal) -> int:
        """Estimate total possessions from minutes played.

        Args:
            minutes: Total minutes played

        Returns:
            Estimated possessions
        """
        return int(minutes * self.possessions_per_minute)

    def _calculate_per_75(self, total: int | Decimal, possessions: int) -> Decimal:
        """Calculate per-75 rate for a stat.

        Args:
            total: Total count of the stat
            possessions: Total possessions

        Returns:
            Per-75 rate, or 0 if below threshold
        """
        if possessions < MIN_POSSESSIONS_THRESHOLD:
            return Decimal("0.00")

        rate = (Decimal(str(total)) / Decimal(possessions)) * PER_75_BASE
        return rate.quantize(Decimal("0.01"))

    def calculate_all(
        self,
        possessions: int,
        # Traditional stats
        points: int = 0,
        fgm: int = 0,
        fga: int = 0,
        fg3m: int = 0,
        fg3a: int = 0,
        ftm: int = 0,
        fta: int = 0,
        assists: int = 0,
        turnovers: int = 0,
        rebounds: int = 0,
        offensive_rebounds: int = 0,
        defensive_rebounds: int = 0,
        steals: int = 0,
        blocks: int = 0,
        # Hustle stats
        deflections: int = 0,
        contested_shots: int = 0,
        contested_2pt: int = 0,
        contested_3pt: int = 0,
        charges_drawn: int = 0,
        loose_balls: int = 0,
        box_outs: int = 0,
        screen_assists: int = 0,
        # Touch stats
        touches: int = 0,
        front_court_touches: int = 0,
    ) -> Per75StatsData:
        """Calculate all per-75 stats from totals.

        Args:
            possessions: Estimated total possessions
            points: Total points
            fgm: Field goals made
            fga: Field goals attempted
            fg3m: 3-pointers made
            fg3a: 3-pointers attempted
            ftm: Free throws made
            fta: Free throws attempted
            assists: Total assists
            turnovers: Total turnovers
            rebounds: Total rebounds
            offensive_rebounds: Offensive rebounds
            defensive_rebounds: Defensive rebounds
            steals: Total steals
            blocks: Total blocks
            deflections: Total deflections
            contested_shots: Total contested shots
            contested_2pt: Contested 2-point shots
            contested_3pt: Contested 3-point shots
            charges_drawn: Charges drawn
            loose_balls: Loose balls recovered
            box_outs: Total box outs
            screen_assists: Screen assists
            touches: Total touches
            front_court_touches: Front court touches

        Returns:
            Per75StatsData with all calculated rates
        """
        return Per75StatsData(
            # Scoring
            pts_per_75=self._calculate_per_75(points, possessions),
            fgm_per_75=self._calculate_per_75(fgm, possessions),
            fga_per_75=self._calculate_per_75(fga, possessions),
            fg3m_per_75=self._calculate_per_75(fg3m, possessions),
            fg3a_per_75=self._calculate_per_75(fg3a, possessions),
            ftm_per_75=self._calculate_per_75(ftm, possessions),
            fta_per_75=self._calculate_per_75(fta, possessions),
            # Playmaking
            ast_per_75=self._calculate_per_75(assists, possessions),
            tov_per_75=self._calculate_per_75(turnovers, possessions),
            # Rebounding
            reb_per_75=self._calculate_per_75(rebounds, possessions),
            oreb_per_75=self._calculate_per_75(offensive_rebounds, possessions),
            dreb_per_75=self._calculate_per_75(defensive_rebounds, possessions),
            # Defense
            stl_per_75=self._calculate_per_75(steals, possessions),
            blk_per_75=self._calculate_per_75(blocks, possessions),
            # Hustle
            deflections_per_75=self._calculate_per_75(deflections, possessions),
            contested_shots_per_75=self._calculate_per_75(contested_shots, possessions),
            contested_2pt_per_75=self._calculate_per_75(contested_2pt, possessions),
            contested_3pt_per_75=self._calculate_per_75(contested_3pt, possessions),
            charges_drawn_per_75=self._calculate_per_75(charges_drawn, possessions),
            loose_balls_per_75=self._calculate_per_75(loose_balls, possessions),
            box_outs_per_75=self._calculate_per_75(box_outs, possessions),
            screen_assists_per_75=self._calculate_per_75(screen_assists, possessions),
            # Ball handling
            touches_per_75=self._calculate_per_75(touches, possessions),
            front_court_touches_per_75=self._calculate_per_75(front_court_touches, possessions),
            # Reference
            possessions_used=possessions,
        )


# Singleton instance
per_75_calculator = Per75Calculator()
