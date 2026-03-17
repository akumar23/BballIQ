"""Service for calculating 8-dimension radar chart percentiles.

Each dimension is a composite of related statistics. Players are ranked
among all qualifying peers, and rank positions are converted to
percentiles (0-100).

Dimensions:
    1. Scoring     - Points per game + true shooting %
    2. Playmaking  - Assists, assist %, turnover control
    3. Defense     - Steals, blocks, DFG% differential, deflections
    4. Efficiency  - TS%, eFG%, turnover rate
    5. Volume      - FGA, usage rate, minutes per game
    6. Durability  - Games played
    7. Clutch      - Clutch points + clutch plus/minus
    8. Versatility - Play type diversity

The composite weights emphasize the most signal-rich sub-stat in each
dimension while still rewarding breadth.
"""

from dataclasses import dataclass
from decimal import Decimal

# Default percentile for missing optional fields
DEFAULT_PERCENTILE = 50

# Minimum minutes for a player to qualify
MIN_MINUTES_THRESHOLD = Decimal("100")


@dataclass
class RadarInput:
    """Input data for radar chart percentile calculation."""

    player_id: int
    # Scoring
    ppg: Decimal
    ts_pct: Decimal
    # Playmaking
    apg: Decimal
    ast_pct: Decimal
    tov_per_game: Decimal
    # Defense
    stl_per_game: Decimal
    blk_per_game: Decimal
    dfg_pct_diff: Decimal | None  # from defensive stats, can be None
    deflections_per_game: Decimal
    # Efficiency
    efg_pct: Decimal
    usg_pct: Decimal
    # Volume
    fga_per_game: Decimal
    mpg: Decimal
    # Durability
    games_played: int
    # Clutch
    clutch_pts: Decimal | None
    clutch_plus_minus: Decimal | None
    # Versatility (play type diversity)
    play_type_count: int  # number of play types with >5% frequency


@dataclass
class RadarResult:
    """Output radar chart percentiles (0-100 per dimension)."""

    player_id: int
    scoring: int
    playmaking: int
    defense: int
    efficiency: int
    volume: int
    durability: int
    clutch: int
    versatility: int


class RadarCalculator:
    """Calculates 8-dimension radar chart percentiles.

    Each dimension is a composite of related stats, ranked as a
    percentile (0-100) among all qualifying players. Higher is better
    in all dimensions.

    Usage::

        calculator = RadarCalculator()
        results = calculator.calculate_all(players)
        # results: dict[player_id, RadarResult]
    """

    def _rank_to_percentiles(self, values: dict[int, Decimal | int]) -> dict[int, int]:
        """Convert raw values to percentile ranks (0-100).

        Players with the same value receive the same percentile
        (average rank method).

        Args:
            values: Dict mapping player_id to a numeric value.

        Returns:
            Dict mapping player_id to percentile (0-100).
        """
        if not values:
            return {}

        n = len(values)
        if n == 1:
            pid = next(iter(values))
            return {pid: 50}

        # Sort by value ascending
        sorted_items = sorted(values.items(), key=lambda x: x[1])

        # Assign ranks (1-based), handling ties with average rank
        ranks: dict[int, float] = {}
        i = 0
        while i < n:
            j = i
            # Find all items with the same value
            while j < n and sorted_items[j][1] == sorted_items[i][1]:
                j += 1
            # Average rank for the tie group
            avg_rank = (i + j + 1) / 2  # 1-based
            for k in range(i, j):
                ranks[sorted_items[k][0]] = avg_rank
            i = j

        # Convert rank to percentile: (rank - 0.5) / n * 100
        percentiles: dict[int, int] = {}
        for pid, rank in ranks.items():
            pct = (rank - 0.5) / n * 100
            percentiles[pid] = max(0, min(100, int(round(pct))))

        return percentiles

    def _compute_scoring(
        self,
        ppg_pct: dict[int, int],
        ts_pct_pct: dict[int, int],
    ) -> dict[int, int]:
        """Compute scoring composite: 0.6 * ppg + 0.4 * ts_pct.

        Args:
            ppg_pct: PPG percentiles.
            ts_pct_pct: TS% percentiles.

        Returns:
            Scoring composite percentiles.
        """
        result: dict[int, int] = {}
        for pid in ppg_pct:
            composite = 0.6 * ppg_pct[pid] + 0.4 * ts_pct_pct.get(pid, DEFAULT_PERCENTILE)
            result[pid] = max(0, min(100, int(round(composite))))
        return result

    def _compute_playmaking(
        self,
        apg_pct: dict[int, int],
        ast_pct_pct: dict[int, int],
        tov_pct: dict[int, int],
    ) -> dict[int, int]:
        """Compute playmaking composite: 0.5 * apg + 0.3 * ast_pct + 0.2 * (100 - tov).

        Low turnovers are good, so we invert the turnover percentile.

        Args:
            apg_pct: APG percentiles.
            ast_pct_pct: AST% percentiles.
            tov_pct: Turnovers per game percentiles (higher = more turnovers).

        Returns:
            Playmaking composite percentiles.
        """
        result: dict[int, int] = {}
        for pid in apg_pct:
            tov_inverted = 100 - tov_pct.get(pid, DEFAULT_PERCENTILE)
            composite = (
                0.5 * apg_pct[pid]
                + 0.3 * ast_pct_pct.get(pid, DEFAULT_PERCENTILE)
                + 0.2 * tov_inverted
            )
            result[pid] = max(0, min(100, int(round(composite))))
        return result

    def _compute_defense(
        self,
        stl_pct: dict[int, int],
        blk_pct: dict[int, int],
        dfg_diff_pct: dict[int, int],
        defl_pct: dict[int, int],
    ) -> dict[int, int]:
        """Compute defense composite: 0.25 each for stl, blk, dfg_diff, deflections.

        Args:
            stl_pct: Steals percentiles.
            blk_pct: Blocks percentiles.
            dfg_diff_pct: DFG% diff percentiles.
            defl_pct: Deflections percentiles.

        Returns:
            Defense composite percentiles.
        """
        result: dict[int, int] = {}
        all_pids = set(stl_pct) | set(blk_pct) | set(defl_pct)
        for pid in all_pids:
            composite = (
                0.25 * stl_pct.get(pid, DEFAULT_PERCENTILE)
                + 0.25 * blk_pct.get(pid, DEFAULT_PERCENTILE)
                + 0.25 * dfg_diff_pct.get(pid, DEFAULT_PERCENTILE)
                + 0.25 * defl_pct.get(pid, DEFAULT_PERCENTILE)
            )
            result[pid] = max(0, min(100, int(round(composite))))
        return result

    def _compute_efficiency(
        self,
        ts_pct_pct: dict[int, int],
        efg_pct_pct: dict[int, int],
        tov_pct: dict[int, int],
    ) -> dict[int, int]:
        """Compute efficiency composite: 0.5 * ts + 0.3 * efg + 0.2 * (100 - tov_rate).

        Args:
            ts_pct_pct: TS% percentiles.
            efg_pct_pct: eFG% percentiles.
            tov_pct: Turnover percentiles (higher = more turnovers).

        Returns:
            Efficiency composite percentiles.
        """
        result: dict[int, int] = {}
        for pid in ts_pct_pct:
            tov_inverted = 100 - tov_pct.get(pid, DEFAULT_PERCENTILE)
            composite = (
                0.5 * ts_pct_pct[pid]
                + 0.3 * efg_pct_pct.get(pid, DEFAULT_PERCENTILE)
                + 0.2 * tov_inverted
            )
            result[pid] = max(0, min(100, int(round(composite))))
        return result

    def _compute_volume(
        self,
        fga_pct: dict[int, int],
        usg_pct: dict[int, int],
        mpg_pct: dict[int, int],
    ) -> dict[int, int]:
        """Compute volume composite: 0.5 * fga + 0.3 * usg + 0.2 * mpg.

        Args:
            fga_pct: FGA per game percentiles.
            usg_pct: Usage rate percentiles.
            mpg_pct: Minutes per game percentiles.

        Returns:
            Volume composite percentiles.
        """
        result: dict[int, int] = {}
        for pid in fga_pct:
            composite = (
                0.5 * fga_pct[pid]
                + 0.3 * usg_pct.get(pid, DEFAULT_PERCENTILE)
                + 0.2 * mpg_pct.get(pid, DEFAULT_PERCENTILE)
            )
            result[pid] = max(0, min(100, int(round(composite))))
        return result

    def _compute_clutch(
        self,
        clutch_pts_pct: dict[int, int],
        clutch_pm_pct: dict[int, int],
        all_pids: set[int],
    ) -> dict[int, int]:
        """Compute clutch composite: 0.5 * clutch_pts + 0.5 * clutch_plus_minus.

        Players with None clutch data get DEFAULT_PERCENTILE (50).

        Args:
            clutch_pts_pct: Clutch points percentiles.
            clutch_pm_pct: Clutch plus/minus percentiles.
            all_pids: Set of all qualifying player IDs.

        Returns:
            Clutch composite percentiles.
        """
        result: dict[int, int] = {}
        for pid in all_pids:
            pts_p = clutch_pts_pct.get(pid, DEFAULT_PERCENTILE)
            pm_p = clutch_pm_pct.get(pid, DEFAULT_PERCENTILE)
            composite = 0.5 * pts_p + 0.5 * pm_p
            result[pid] = max(0, min(100, int(round(composite))))
        return result

    def calculate_all(self, players: list[RadarInput]) -> dict[int, RadarResult]:
        """Calculate 8-dimension radar percentiles for all qualifying players.

        For each dimension:
        1. Compute raw values for component stats
        2. Rank all players to get component percentiles
        3. Combine component percentiles with dimension weights

        Args:
            players: List of player radar input data.

        Returns:
            Dict mapping player_id to RadarResult.
        """
        # Filter qualifying players (minimum minutes threshold via mpg proxy)
        qualifying = [p for p in players if p.mpg * Decimal(p.games_played) >= MIN_MINUTES_THRESHOLD]

        if not qualifying:
            return {}

        all_pids = {p.player_id for p in qualifying}

        # --- Build raw value dicts for each sub-stat ---

        ppg_vals: dict[int, Decimal] = {}
        ts_vals: dict[int, Decimal] = {}
        apg_vals: dict[int, Decimal] = {}
        ast_pct_vals: dict[int, Decimal] = {}
        tov_vals: dict[int, Decimal] = {}
        stl_vals: dict[int, Decimal] = {}
        blk_vals: dict[int, Decimal] = {}
        dfg_diff_vals: dict[int, Decimal] = {}
        defl_vals: dict[int, Decimal] = {}
        efg_vals: dict[int, Decimal] = {}
        usg_vals: dict[int, Decimal] = {}
        fga_vals: dict[int, Decimal] = {}
        mpg_vals: dict[int, Decimal] = {}
        gp_vals: dict[int, int] = {}
        clutch_pts_vals: dict[int, Decimal] = {}
        clutch_pm_vals: dict[int, Decimal] = {}
        versatility_vals: dict[int, int] = {}

        for p in qualifying:
            pid = p.player_id
            ppg_vals[pid] = p.ppg
            ts_vals[pid] = p.ts_pct
            apg_vals[pid] = p.apg
            ast_pct_vals[pid] = p.ast_pct
            tov_vals[pid] = p.tov_per_game
            stl_vals[pid] = p.stl_per_game
            blk_vals[pid] = p.blk_per_game
            defl_vals[pid] = p.deflections_per_game
            efg_vals[pid] = p.efg_pct
            usg_vals[pid] = p.usg_pct
            fga_vals[pid] = p.fga_per_game
            mpg_vals[pid] = p.mpg
            gp_vals[pid] = p.games_played
            versatility_vals[pid] = p.play_type_count

            # DFG% diff: lower is better (player makes opponents shoot worse),
            # so we invert by negating so that ranking treats lower raw as higher rank
            if p.dfg_pct_diff is not None:
                dfg_diff_vals[pid] = -p.dfg_pct_diff  # negate: lower diff = better defense

            if p.clutch_pts is not None:
                clutch_pts_vals[pid] = p.clutch_pts
            if p.clutch_plus_minus is not None:
                clutch_pm_vals[pid] = p.clutch_plus_minus

        # --- Rank each sub-stat to percentiles ---

        ppg_pct = self._rank_to_percentiles(ppg_vals)
        ts_pct_pct = self._rank_to_percentiles(ts_vals)
        apg_pct = self._rank_to_percentiles(apg_vals)
        ast_pct_pct = self._rank_to_percentiles(ast_pct_vals)
        tov_pct = self._rank_to_percentiles(tov_vals)
        stl_pct = self._rank_to_percentiles(stl_vals)
        blk_pct = self._rank_to_percentiles(blk_vals)
        dfg_diff_pct = self._rank_to_percentiles(dfg_diff_vals)
        defl_pct = self._rank_to_percentiles(defl_vals)
        efg_pct_pct = self._rank_to_percentiles(efg_vals)
        usg_pct_pct = self._rank_to_percentiles(usg_vals)
        fga_pct = self._rank_to_percentiles(fga_vals)
        mpg_pct = self._rank_to_percentiles(mpg_vals)
        gp_pct = self._rank_to_percentiles(gp_vals)
        clutch_pts_pct = self._rank_to_percentiles(clutch_pts_vals)
        clutch_pm_pct = self._rank_to_percentiles(clutch_pm_vals)
        versatility_pct = self._rank_to_percentiles(versatility_vals)

        # --- Compute composite dimensions ---

        scoring = self._compute_scoring(ppg_pct, ts_pct_pct)
        playmaking = self._compute_playmaking(apg_pct, ast_pct_pct, tov_pct)
        defense = self._compute_defense(stl_pct, blk_pct, dfg_diff_pct, defl_pct)
        efficiency = self._compute_efficiency(ts_pct_pct, efg_pct_pct, tov_pct)
        volume = self._compute_volume(fga_pct, usg_pct_pct, mpg_pct)
        clutch = self._compute_clutch(clutch_pts_pct, clutch_pm_pct, all_pids)

        # --- Assemble results ---

        results: dict[int, RadarResult] = {}
        for pid in all_pids:
            results[pid] = RadarResult(
                player_id=pid,
                scoring=scoring.get(pid, DEFAULT_PERCENTILE),
                playmaking=playmaking.get(pid, DEFAULT_PERCENTILE),
                defense=defense.get(pid, DEFAULT_PERCENTILE),
                efficiency=efficiency.get(pid, DEFAULT_PERCENTILE),
                volume=volume.get(pid, DEFAULT_PERCENTILE),
                durability=gp_pct.get(pid, DEFAULT_PERCENTILE),
                clutch=clutch.get(pid, DEFAULT_PERCENTILE),
                versatility=versatility_pct.get(pid, DEFAULT_PERCENTILE),
            )

        return results
