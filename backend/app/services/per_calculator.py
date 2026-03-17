"""Service for calculating Player Efficiency Rating (PER).

Implements the full Basketball Reference PER formula, which produces a
per-minute rating calibrated so that the league average is always 15.0.

The three-step process:
1. Compute unadjusted PER (uPER) from box-score stats
2. Pace-adjust: aPER = (lg_Pace / team_Pace) * uPER
3. Normalize so the minutes-weighted league average equals 15.0

References:
    - Basketball Reference PER page
    - John Hollinger, "Pro Basketball Forecast" (2005)
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

# Minimum minutes for a player to qualify for PER calculation
MIN_MINUTES_THRESHOLD = Decimal("100")

# Target league-average PER
LEAGUE_AVG_PER = Decimal("15.0")

# Quantization for final output
TWO_PLACES = Decimal("0.01")


@dataclass
class TeamStats:
    """Team totals for a season."""

    team_id: int
    team_abbreviation: str
    games_played: int
    minutes: Decimal
    fgm: int
    fga: int
    fg3m: int
    ast: int
    ftm: int
    fta: int
    orb: int
    trb: int  # total rebounds
    tov: int
    pf: int  # personal fouls
    pts: int
    pace: Decimal


@dataclass
class LeagueStats:
    """League-wide aggregates (sum of all teams)."""

    ast: int
    fgm: int
    ftm: int
    fta: int
    pts: int
    fga: int
    orb: int
    trb: int
    tov: int
    pf: int
    pace: Decimal  # league average pace


@dataclass
class PlayerPERData:
    """Input data for PER calculation."""

    player_id: int
    team_abbreviation: str
    minutes: Decimal
    fg3m: int
    ast: int
    fgm: int
    ftm: int
    fta: int
    fga: int
    tov: int
    orb: int
    drb: int
    trb: int
    stl: int
    blk: int
    pf: int
    pts: int


class PERCalculator:
    """Calculator for Player Efficiency Rating.

    Pre-computes league-level constants at construction time so that
    individual player calculations are fast. Expects league and team
    aggregates to be supplied externally (e.g. from the NBA API or
    database aggregation).

    Usage::

        calculator = PERCalculator(league_stats, team_stats_by_abbr)
        results = calculator.calculate_all(players)
        # results: dict[player_id, Decimal]
    """

    def __init__(
        self,
        league_stats: LeagueStats,
        team_stats: dict[str, TeamStats],
    ):
        """Initialize with league and team aggregates.

        Args:
            league_stats: League-wide totals for the season.
            team_stats: Team totals keyed by team abbreviation.
        """
        self.league_stats = league_stats
        self.team_stats = team_stats

        lg = league_stats

        # Guard against division by zero in degenerate data
        lg_fg = Decimal(lg.fgm) if lg.fgm else Decimal("1")
        lg_ft = Decimal(lg.ftm) if lg.ftm else Decimal("1")
        lg_fta = Decimal(lg.fta) if lg.fta else Decimal("1")
        lg_fga = Decimal(lg.fga) if lg.fga else Decimal("1")
        lg_trb = Decimal(lg.trb) if lg.trb else Decimal("1")
        lg_pf = Decimal(lg.pf) if lg.pf else Decimal("1")

        # Pre-compute league constants
        # factor = (2/3) - (0.5 * (lg_AST / lg_FG)) / (2 * (lg_FG / lg_FT))
        self._factor = (
            Decimal("2") / Decimal("3")
            - (Decimal("0.5") * (Decimal(lg.ast) / lg_fg))
            / (Decimal("2") * (lg_fg / lg_ft))
        )

        # VOP = lg_PTS / (lg_FGA - lg_ORB + lg_TOV + 0.44 * lg_FTA)
        vop_denominator = lg_fga - Decimal(lg.orb) + Decimal(lg.tov) + Decimal("0.44") * lg_fta
        self._vop = Decimal(lg.pts) / vop_denominator if vop_denominator else Decimal("0")

        # DRB% = (lg_TRB - lg_ORB) / lg_TRB
        self._drb_pct = (lg_trb - Decimal(lg.orb)) / lg_trb

        # League FTM/PF and FTA/PF ratios (used in foul penalty term)
        self._lg_ftm_per_pf = Decimal(lg.ftm) / lg_pf
        self._lg_fta_per_pf = lg_fta / lg_pf

        self._lg_pace = lg.pace

    def _calculate_uper(self, player: PlayerPERData) -> Decimal | None:
        """Calculate unadjusted PER for a single player.

        Args:
            player: Box-score totals for the player.

        Returns:
            Unadjusted PER value, or None if the player does not qualify.
        """
        if player.minutes < MIN_MINUTES_THRESHOLD:
            return None

        team = self.team_stats.get(player.team_abbreviation)
        if team is None:
            return None

        # Team-level ratios (guard against zero)
        team_fgm = Decimal(team.fgm) if team.fgm else Decimal("1")
        team_ast_ratio = Decimal(team.ast) / team_fgm

        mp = player.minutes

        # Build each term of the uPER formula
        term_3pm = Decimal(player.fg3m)

        term_ast = Decimal("2") / Decimal("3") * Decimal(player.ast)

        term_fgm = (
            (Decimal("2") - self._factor * team_ast_ratio) * Decimal(player.fgm)
        )

        term_ftm = (
            Decimal(player.ftm)
            * Decimal("0.5")
            * (
                Decimal("1")
                + (Decimal("1") - team_ast_ratio)
                + Decimal("2") / Decimal("3") * team_ast_ratio
            )
        )

        term_tov = -self._vop * Decimal(player.tov)

        term_missed_fg = (
            -self._vop * self._drb_pct * (Decimal(player.fga) - Decimal(player.fgm))
        )

        term_missed_ft = (
            -self._vop
            * Decimal("0.44")
            * (Decimal("0.44") + Decimal("0.56") * self._drb_pct)
            * (Decimal(player.fta) - Decimal(player.ftm))
        )

        term_drb = self._vop * (Decimal("1") - self._drb_pct) * (Decimal(player.trb) - Decimal(player.orb))

        term_orb = self._vop * self._drb_pct * Decimal(player.orb)

        term_stl = self._vop * Decimal(player.stl)

        term_blk = self._vop * self._drb_pct * Decimal(player.blk)

        term_pf = (
            -Decimal(player.pf)
            * (
                self._lg_ftm_per_pf
                - Decimal("0.44") * self._lg_fta_per_pf * self._vop
            )
        )

        numerator = (
            term_3pm
            + term_ast
            + term_fgm
            + term_ftm
            + term_tov
            + term_missed_fg
            + term_missed_ft
            + term_drb
            + term_orb
            + term_stl
            + term_blk
            + term_pf
        )

        uper = numerator / mp
        return uper

    def _pace_adjust(self, uper: Decimal, team_abbreviation: str) -> Decimal:
        """Apply pace adjustment: aPER = (lg_Pace / team_Pace) * uPER.

        Args:
            uper: Unadjusted PER.
            team_abbreviation: Team abbreviation for pace lookup.

        Returns:
            Pace-adjusted PER.
        """
        team = self.team_stats.get(team_abbreviation)
        if team is None or team.pace == 0:
            return uper

        return (self._lg_pace / team.pace) * uper

    def calculate(self, player: PlayerPERData) -> Decimal | None:
        """Calculate pace-adjusted PER for a single player (pre-normalization).

        This returns the pace-adjusted but NOT league-normalized PER.
        For the final, league-normalized PER, use ``calculate_all``.

        Args:
            player: Box-score totals for the player.

        Returns:
            Pace-adjusted PER, or None if the player does not qualify.
        """
        uper = self._calculate_uper(player)
        if uper is None:
            return None

        return self._pace_adjust(uper, player.team_abbreviation)

    def calculate_all(self, players: list[PlayerPERData]) -> dict[int, Decimal]:
        """Calculate fully normalized PER for all qualifying players.

        The normalization step scales every player's pace-adjusted PER so
        that the minutes-weighted league average equals 15.0.

        Args:
            players: List of player box-score data.

        Returns:
            Dict mapping player_id to final PER (quantized to 2 decimals).
        """
        # Step 1 + 2: Compute pace-adjusted PER for each qualifying player
        aper_map: dict[int, Decimal] = {}
        minutes_map: dict[int, Decimal] = {}

        for player in players:
            aper = self.calculate(player)
            if aper is not None:
                aper_map[player.player_id] = aper
                minutes_map[player.player_id] = player.minutes

        if not aper_map:
            return {}

        # Step 3: Compute minutes-weighted league average aPER
        total_minutes = sum(minutes_map.values())
        if total_minutes == 0:
            return {}

        weighted_aper_sum = sum(
            aper_map[pid] * minutes_map[pid] for pid in aper_map
        )
        lg_aper = weighted_aper_sum / total_minutes

        # Normalization factor so that lg_aPER maps to 15.0
        if lg_aper == 0:
            return {}

        normalization_factor = LEAGUE_AVG_PER / lg_aper

        # Apply normalization and quantize
        results: dict[int, Decimal] = {}
        for pid, aper in aper_map.items():
            per = (aper * normalization_factor).quantize(TWO_PLACES, rounding=ROUND_HALF_UP)
            results[pid] = per

        return results
