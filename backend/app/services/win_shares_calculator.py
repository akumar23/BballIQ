"""Service for calculating Win Shares (WS).

Win Shares credits players for their contributions to team wins,
splitting into offensive (OWS) and defensive (DWS) components.

Since the platform already has individual offensive and defensive
ratings from the NBA.com Advanced stats endpoint, we use a simplified
formula that leverages those pre-computed ratings:

    OWS = marginal_offense / marginal_pts_per_win
    DWS = marginal_defense / marginal_pts_per_win

Where:
    marginal_offense = (player_ORtg/100 - 0.92 * lg_PPP) * player_possessions
    marginal_defense = (MP/Team_MP) * Team_Def_Poss * (1.08 * lg_PPP - player_DRtg/100)
    marginal_pts_per_win = 0.32 * lg_PPG * (team_pace / lg_pace)

References:
    - Basketball Reference Win Shares methodology
    - Dean Oliver, "Basketball on Paper" (2004)
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

# Minimum minutes for a player to qualify
MIN_MINUTES_THRESHOLD = Decimal("100")

# Marginal offense/defense multipliers
MARGINAL_OFFENSE_FACTOR = Decimal("0.92")
MARGINAL_DEFENSE_FACTOR = Decimal("1.08")

# Marginal points per win multiplier
MARGINAL_PTS_PER_WIN_FACTOR = Decimal("0.32")

# Minutes per game for WS/48 calculation
MINUTES_PER_GAME = Decimal("48")

# Possessions per minute estimate (league average ~2.08)
POSSESSIONS_PER_MINUTE = Decimal("2.08")

# Quantization for output
TWO_PLACES = Decimal("0.01")
FOUR_PLACES = Decimal("0.0001")


@dataclass
class WinSharesInput:
    """Input data for Win Shares calculation."""

    player_id: int
    team_abbreviation: str
    minutes: Decimal
    # From PlayerAdvancedStats (already fetched from NBA API)
    off_rating: Decimal  # individual ORtg from NBA.com
    def_rating: Decimal  # individual DRtg from NBA.com
    # Team context
    team_minutes: Decimal
    team_pace: Decimal
    team_def_possessions: Decimal


@dataclass
class WinSharesResult:
    """Output of Win Shares calculation."""

    player_id: int
    ows: Decimal  # Offensive Win Shares
    dws: Decimal  # Defensive Win Shares
    ws: Decimal  # Total Win Shares
    ws_per_48: Decimal  # Win Shares per 48 minutes


class WinSharesCalculator:
    """Win Shares calculator using NBA.com's ORtg/DRtg.

    Since individual offensive and defensive ratings are already
    available from the Advanced stats endpoint, the calculation
    is streamlined compared to the full Basketball Reference
    derivation.

    Usage::

        calculator = WinSharesCalculator(
            league_ppg=Decimal("112.5"),
            league_pace=Decimal("100.3"),
            league_ppp=Decimal("1.125"),
        )
        results = calculator.calculate_all(players)
        # results: dict[player_id, WinSharesResult]
    """

    def __init__(
        self,
        league_ppg: Decimal,
        league_pace: Decimal,
        league_ppp: Decimal,
    ):
        """Initialize with league-wide context.

        Args:
            league_ppg: League average points per game.
            league_pace: League average pace (possessions per 48 minutes).
            league_ppp: League average points per possession.
        """
        self.league_ppg = league_ppg
        self.league_pace = league_pace
        self.league_ppp = league_ppp

    def _estimate_player_possessions(self, minutes: Decimal) -> Decimal:
        """Estimate a player's individual possessions from minutes.

        Args:
            minutes: Total minutes played.

        Returns:
            Estimated possessions.
        """
        return minutes * POSSESSIONS_PER_MINUTE

    def _calculate_marginal_pts_per_win(self, team_pace: Decimal) -> Decimal:
        """Calculate marginal points per win for a team's pace.

        marginal_pts_per_win = 0.32 * lg_PPG * (team_pace / lg_pace)

        Args:
            team_pace: Team pace (possessions per 48 minutes).

        Returns:
            Marginal points per win.
        """
        if self.league_pace == 0:
            return Decimal("1")  # Guard against division by zero

        pace_ratio = team_pace / self.league_pace
        return MARGINAL_PTS_PER_WIN_FACTOR * self.league_ppg * pace_ratio

    def _calculate_ows(
        self,
        off_rating: Decimal,
        player_possessions: Decimal,
        marginal_pts_per_win: Decimal,
    ) -> Decimal:
        """Calculate Offensive Win Shares.

        OWS = marginal_offense / marginal_pts_per_win
        marginal_offense = (player_ORtg/100 - 0.92 * lg_PPP) * player_possessions

        Args:
            off_rating: Player's individual offensive rating.
            player_possessions: Estimated player possessions.
            marginal_pts_per_win: Points needed per marginal win.

        Returns:
            Offensive Win Shares (floored at 0).
        """
        if marginal_pts_per_win == 0:
            return Decimal("0")

        player_ppp = off_rating / Decimal("100")
        marginal_offense = (player_ppp - MARGINAL_OFFENSE_FACTOR * self.league_ppp) * player_possessions

        ows = marginal_offense / marginal_pts_per_win

        # OWS can be negative for very inefficient players; floor at 0
        # per Basketball Reference convention
        return max(Decimal("0"), ows)

    def _calculate_dws(
        self,
        def_rating: Decimal,
        minutes: Decimal,
        team_minutes: Decimal,
        team_def_possessions: Decimal,
        marginal_pts_per_win: Decimal,
    ) -> Decimal:
        """Calculate Defensive Win Shares.

        DWS = marginal_defense / marginal_pts_per_win
        marginal_defense = (MP/Team_MP) * Team_Def_Poss * (1.08 * lg_PPP - player_DRtg/100)

        Args:
            def_rating: Player's individual defensive rating.
            minutes: Player's total minutes.
            team_minutes: Team's total minutes.
            team_def_possessions: Team's total defensive possessions.
            marginal_pts_per_win: Points needed per marginal win.

        Returns:
            Defensive Win Shares (floored at 0).
        """
        if marginal_pts_per_win == 0 or team_minutes == 0:
            return Decimal("0")

        minutes_share = minutes / team_minutes
        player_dpp = def_rating / Decimal("100")
        marginal_defense = (
            minutes_share
            * team_def_possessions
            * (MARGINAL_DEFENSE_FACTOR * self.league_ppp - player_dpp)
        )

        dws = marginal_defense / marginal_pts_per_win

        # DWS can be negative for poor defenders; floor at 0
        return max(Decimal("0"), dws)

    def calculate(self, player: WinSharesInput) -> WinSharesResult | None:
        """Calculate Win Shares for a single player.

        Args:
            player: Player input data.

        Returns:
            WinSharesResult, or None if the player does not qualify.
        """
        if player.minutes < MIN_MINUTES_THRESHOLD:
            return None

        if player.team_pace == 0 or player.team_minutes == 0:
            return None

        marginal_pts_per_win = self._calculate_marginal_pts_per_win(player.team_pace)
        player_possessions = self._estimate_player_possessions(player.minutes)

        ows = self._calculate_ows(
            player.off_rating,
            player_possessions,
            marginal_pts_per_win,
        )

        dws = self._calculate_dws(
            player.def_rating,
            player.minutes,
            player.team_minutes,
            player.team_def_possessions,
            marginal_pts_per_win,
        )

        ws = ows + dws

        # WS/48: Win Shares per 48 minutes played
        ws_per_48 = (ws / player.minutes * MINUTES_PER_GAME) if player.minutes > 0 else Decimal("0")

        return WinSharesResult(
            player_id=player.player_id,
            ows=ows.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
            dws=dws.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
            ws=ws.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
            ws_per_48=ws_per_48.quantize(FOUR_PLACES, rounding=ROUND_HALF_UP),
        )

    def calculate_all(self, players: list[WinSharesInput]) -> dict[int, WinSharesResult]:
        """Calculate Win Shares for all qualifying players.

        Args:
            players: List of player input data.

        Returns:
            Dict mapping player_id to WinSharesResult.
        """
        results: dict[int, WinSharesResult] = {}

        for player in players:
            result = self.calculate(player)
            if result is not None:
                results[player.player_id] = result

        return results
