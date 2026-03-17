"""Service for calculating Box Plus/Minus (BPM) and Value Over Replacement Player (VORP).

Implements a simplified BPM 2.0 calculator that estimates a player's
per-100-possession contribution above league average using box-score
statistics, position context, and team adjustment.

VORP converts BPM into a cumulative, counting stat:
    VORP = [BPM - (-2.0)] * (% of team minutes) * (team_games / 82)

The replacement level of -2.0 represents a readily available minor-league
or end-of-bench player.

References:
    - Basketball Reference BPM methodology
    - Daniel Myers, "About Box Plus/Minus (BPM)"
"""

from dataclasses import dataclass
from decimal import Decimal, ROUND_HALF_UP

# Minimum minutes for a player to qualify
MIN_MINUTES_THRESHOLD = Decimal("100")

# Replacement level BPM (a freely available player)
REPLACEMENT_LEVEL = Decimal("-2.0")

# Full season games for VORP prorating
FULL_SEASON_GAMES = 82

# Team minutes per game (5 players x 48 minutes)
TEAM_MINUTES_PER_GAME = Decimal("240")

# Quantization for output
TWO_PLACES = Decimal("0.01")

# League average baselines (typical NBA season)
LEAGUE_AVG_PTS_PER_100 = Decimal("110.0")
LEAGUE_AVG_TS_PCT = Decimal("0.570")
LEAGUE_AVG_USG = Decimal("0.200")

# Position average rebounds per 100 possessions
POSITION_AVG_TRB: dict[str, Decimal] = {
    "G": Decimal("5.5"),
    "G-F": Decimal("6.5"),
    "F-G": Decimal("6.5"),
    "F": Decimal("8.5"),
    "F-C": Decimal("10.0"),
    "C-F": Decimal("10.0"),
    "C": Decimal("12.0"),
}

# Assist coefficient by position archetype
POSITION_AST_COEFF: dict[str, Decimal] = {
    "G": Decimal("0.25"),
    "G-F": Decimal("0.275"),
    "F-G": Decimal("0.275"),
    "F": Decimal("0.30"),
    "F-C": Decimal("0.325"),
    "C-F": Decimal("0.325"),
    "C": Decimal("0.35"),
}


@dataclass
class PlayerBPMInput:
    """Input data for BPM calculation."""

    player_id: int
    team_abbreviation: str
    position: str  # "G", "F", "C" or "G-F", "F-C" etc.
    minutes: Decimal
    games_played: int
    # Per-100 possession stats
    pts_per100: Decimal
    trb_per100: Decimal
    ast_per100: Decimal
    stl_per100: Decimal
    blk_per100: Decimal
    tov_per100: Decimal
    # Efficiency
    ts_pct: Decimal
    usg_pct: Decimal
    # Team context
    team_net_rating: Decimal


@dataclass
class BPMResult:
    """Output of BPM/VORP calculation."""

    player_id: int
    obpm: Decimal
    dbpm: Decimal
    bpm: Decimal
    vorp: Decimal


class BPMCalculator:
    """Simplified BPM 2.0 calculator.

    Estimates offensive and defensive contributions from box-score stats
    using position-aware coefficients. Applies a team adjustment so that
    the minutes-weighted sum of player BPMs on each team equals the
    team's actual net rating.

    Usage::

        calculator = BPMCalculator()
        results = calculator.calculate_all(players)
        # results: dict[player_id, BPMResult]
    """

    # Coefficient weights for raw BPM components
    SCORING_COEFF = Decimal("0.2")
    REBOUND_COEFF = Decimal("0.15")
    STEAL_COEFF = Decimal("0.6")
    BLOCK_COEFF = Decimal("0.35")
    TURNOVER_COEFF = Decimal("-0.35")
    EFFICIENCY_COEFF = Decimal("20")
    USG_PENALTY_THRESHOLD = Decimal("0.05")  # above league avg + this
    USG_PENALTY_COEFF = Decimal("-0.5")

    # Offensive/defensive split ratio for raw BPM
    OFFENSIVE_SHARE = Decimal("0.65")
    DEFENSIVE_SHARE = Decimal("0.35")

    def _normalize_position(self, position: str) -> str:
        """Normalize position string to a known archetype.

        Args:
            position: Raw position string (e.g. "G", "SG", "PF-C").

        Returns:
            Normalized position key for coefficient lookup.
        """
        pos = position.upper().strip()

        # Direct matches
        if pos in POSITION_AVG_TRB:
            return pos

        # Map common NBA position strings
        position_map = {
            "PG": "G",
            "SG": "G",
            "SF": "F",
            "PF": "F",
            "PG-SG": "G",
            "SG-SF": "G-F",
            "SF-PF": "F",
            "PF-C": "F-C",
            "SG-PG": "G",
            "SF-SG": "G-F",
            "PF-SF": "F",
            "C-PF": "C-F",
        }

        return position_map.get(pos, "F")  # Default to forward

    def _calculate_raw_bpm(self, player: PlayerBPMInput) -> Decimal:
        """Calculate raw (pre-team-adjustment) BPM for a player.

        Args:
            player: Per-100-possession stats and context.

        Returns:
            Raw BPM estimate.
        """
        pos = self._normalize_position(player.position)

        # Scoring contribution
        scoring = (player.pts_per100 - LEAGUE_AVG_PTS_PER_100) * self.SCORING_COEFF

        # Assist contribution (position-weighted)
        ast_coeff = POSITION_AST_COEFF.get(pos, Decimal("0.30"))
        assists = player.ast_per100 * ast_coeff

        # Rebounding contribution (relative to position average)
        pos_avg_trb = POSITION_AVG_TRB.get(pos, Decimal("8.5"))
        rebounds = (player.trb_per100 - pos_avg_trb) * self.REBOUND_COEFF

        # Defensive counting stats
        steals = player.stl_per100 * self.STEAL_COEFF
        blocks = player.blk_per100 * self.BLOCK_COEFF

        # Turnover penalty
        turnovers = player.tov_per100 * self.TURNOVER_COEFF

        # Efficiency bonus (TS% relative to league average)
        efficiency = (player.ts_pct - LEAGUE_AVG_TS_PCT) * self.EFFICIENCY_COEFF

        # Usage penalty for high-usage, low-efficiency players
        usg_penalty = Decimal("0")
        usg_over = player.usg_pct - (LEAGUE_AVG_USG + self.USG_PENALTY_THRESHOLD)
        if usg_over > 0:
            # Only penalize if efficiency is below average
            if player.ts_pct < LEAGUE_AVG_TS_PCT:
                usg_penalty = usg_over * self.USG_PENALTY_COEFF * Decimal("100")

        raw_bpm = scoring + assists + rebounds + steals + blocks + turnovers + efficiency + usg_penalty
        return raw_bpm

    def _split_offensive_defensive(
        self,
        raw_bpm: Decimal,
        player: PlayerBPMInput,
    ) -> tuple[Decimal, Decimal]:
        """Split raw BPM into offensive and defensive components.

        Offensive BPM is driven more by scoring, assists, and turnovers.
        Defensive BPM is driven more by steals, blocks, and rebounds.

        Args:
            raw_bpm: Total raw BPM.
            player: Player input data for position context.

        Returns:
            Tuple of (raw_obpm, raw_dbpm).
        """
        pos = self._normalize_position(player.position)

        # Compute offensive-leaning and defensive-leaning sub-scores
        scoring = (player.pts_per100 - LEAGUE_AVG_PTS_PER_100) * self.SCORING_COEFF
        ast_coeff = POSITION_AST_COEFF.get(pos, Decimal("0.30"))
        assists = player.ast_per100 * ast_coeff
        turnovers = player.tov_per100 * self.TURNOVER_COEFF
        efficiency = (player.ts_pct - LEAGUE_AVG_TS_PCT) * self.EFFICIENCY_COEFF

        offensive_signal = scoring + assists + turnovers + efficiency

        pos_avg_trb = POSITION_AVG_TRB.get(pos, Decimal("8.5"))
        rebounds = (player.trb_per100 - pos_avg_trb) * self.REBOUND_COEFF
        steals = player.stl_per100 * self.STEAL_COEFF
        blocks = player.blk_per100 * self.BLOCK_COEFF

        defensive_signal = rebounds + steals + blocks

        total_signal = abs(offensive_signal) + abs(defensive_signal)

        if total_signal == 0:
            return raw_bpm * self.OFFENSIVE_SHARE, raw_bpm * self.DEFENSIVE_SHARE

        off_weight = abs(offensive_signal) / total_signal
        def_weight = abs(defensive_signal) / total_signal

        # Ensure signs are preserved
        raw_obpm = raw_bpm * off_weight
        raw_dbpm = raw_bpm * def_weight

        return raw_obpm, raw_dbpm

    def _apply_team_adjustment(
        self,
        players: list[PlayerBPMInput],
        raw_bpms: dict[int, Decimal],
    ) -> dict[int, Decimal]:
        """Adjust individual BPMs so team totals match actual net rating.

        The gap between the minutes-weighted sum of raw BPMs and the
        actual team net rating is distributed proportionally by minutes.

        Args:
            players: All player inputs.
            raw_bpms: Raw BPM keyed by player_id.

        Returns:
            Team-adjusted BPM keyed by player_id.
        """
        # Group players by team
        teams: dict[str, list[PlayerBPMInput]] = {}
        for player in players:
            if player.player_id in raw_bpms:
                teams.setdefault(player.team_abbreviation, []).append(player)

        adjusted: dict[int, Decimal] = {}

        for team_abbr, team_players in teams.items():
            # Minutes-weighted average raw BPM for the team
            total_minutes = sum(p.minutes for p in team_players)
            if total_minutes == 0:
                for p in team_players:
                    adjusted[p.player_id] = raw_bpms[p.player_id]
                continue

            weighted_bpm_sum = sum(
                raw_bpms[p.player_id] * p.minutes for p in team_players
            )
            team_avg_raw_bpm = weighted_bpm_sum / total_minutes

            # Target is the team's actual net rating
            team_net_rating = team_players[0].team_net_rating

            # Adjustment = difference spread proportionally by minutes
            gap = team_net_rating - team_avg_raw_bpm

            for p in team_players:
                minute_share = p.minutes / total_minutes
                # Distribute proportionally (players with more minutes get more adjustment)
                player_adjustment = gap * minute_share * (total_minutes / p.minutes) if p.minutes > 0 else Decimal("0")
                # Actually, distribute evenly per minute: each player gets the same per-minute adjustment
                # gap is per-minute, so just add gap to each player
                adjusted[p.player_id] = raw_bpms[p.player_id] + gap

        return adjusted

    def _calculate_vorp(
        self,
        bpm: Decimal,
        minutes: Decimal,
        games_played: int,
    ) -> Decimal:
        """Calculate Value Over Replacement Player.

        VORP = [BPM - (-2.0)] * (% of team minutes) * (team_games / 82)

        Args:
            bpm: Final (team-adjusted) BPM.
            minutes: Player's total minutes.
            games_played: Player's games played.

        Returns:
            VORP value.
        """
        team_total_minutes = TEAM_MINUTES_PER_GAME * Decimal(games_played)

        if team_total_minutes == 0:
            return Decimal("0")

        pct_team_minutes = minutes / team_total_minutes
        season_fraction = Decimal(games_played) / Decimal(FULL_SEASON_GAMES)

        vorp = (bpm - REPLACEMENT_LEVEL) * pct_team_minutes * season_fraction
        return vorp

    def calculate_all(self, players: list[PlayerBPMInput]) -> dict[int, BPMResult]:
        """Calculate BPM and VORP for all qualifying players.

        Steps:
        1. Calculate raw BPM for each player
        2. Apply team adjustment
        3. Split into OBPM/DBPM
        4. Calculate VORP

        Args:
            players: List of player input data.

        Returns:
            Dict mapping player_id to BPMResult.
        """
        # Filter to qualifying players
        qualifying = [p for p in players if p.minutes >= MIN_MINUTES_THRESHOLD]

        if not qualifying:
            return {}

        # Step 1: Raw BPM
        raw_bpms: dict[int, Decimal] = {}
        for player in qualifying:
            raw_bpms[player.player_id] = self._calculate_raw_bpm(player)

        # Step 2: Team adjustment
        adjusted_bpms = self._apply_team_adjustment(qualifying, raw_bpms)

        # Step 3 + 4: Split and compute VORP
        results: dict[int, BPMResult] = {}
        player_lookup = {p.player_id: p for p in qualifying}

        for pid, bpm in adjusted_bpms.items():
            player = player_lookup[pid]

            # Split into OBPM/DBPM using the adjusted total
            raw_obpm, raw_dbpm = self._split_offensive_defensive(bpm, player)

            vorp = self._calculate_vorp(bpm, player.minutes, player.games_played)

            results[pid] = BPMResult(
                player_id=pid,
                obpm=raw_obpm.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
                dbpm=raw_dbpm.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
                bpm=bpm.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
                vorp=vorp.quantize(TWO_PLACES, rounding=ROUND_HALF_UP),
            )

        return results
