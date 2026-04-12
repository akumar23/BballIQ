"""Service for computing luck-adjusted metrics for NBA players.

Luck-adjusted metrics isolate sustainable skill from variance-driven
outcomes by comparing actual results to expected values derived from
Pythagorean win expectation, clutch shooting regression, and garbage
time estimation.
"""

from __future__ import annotations

from app.services.metrics_utils import safe_div, safe_float


# Minimum games required for clutch EPA calculation
MIN_CLUTCH_GAMES = 10

# Default Pythagorean exponent (Morey refined value for NBA)
DEFAULT_PYTHAGOREAN_EXPONENT = 14.23

# Free throw weight in true shooting attempts (standard NBA formula)
FTA_TSA_WEIGHT = 0.44


class LuckAdjustedCalculator:
    """Calculator for luck-adjusted player metrics.

    Provides expected wins (Pythagorean), clutch EPA, and garbage time
    estimates to help separate repeatable skill from single-season noise.
    """

    @staticmethod
    def pythagorean_expected_wins(
        pts_for: float,
        pts_against: float,
        games: int,
        exponent: float = DEFAULT_PYTHAGOREAN_EXPONENT,
    ) -> float:
        """Estimate expected wins using the Pythagorean expectation formula.

        Win% = PF^exp / (PF^exp + PA^exp), then scaled to the number
        of games played.

        Args:
            pts_for: Total points scored by the team.
            pts_against: Total points allowed by the team.
            games: Number of games played.
            exponent: Pythagorean exponent (default 14.23, Morey refined).

        Returns:
            Expected wins over the given number of games.
        """
        if pts_for <= 0 or pts_against <= 0:
            return games / 2.0

        pf_exp = pts_for**exponent
        pa_exp = pts_against**exponent
        win_pct = safe_div(pf_exp, pf_exp + pa_exp, default=0.5)

        return win_pct * games

    def player_expected_wins(
        self,
        on_off: object,
        season_stats: object,
        team_stats: dict[str, float | int],
        league_pace: float,
    ) -> float:
        """Estimate a player's expected win contribution via on/off splits.

        Computes Pythagorean expected wins for the team with the player
        on court versus off court, then attributes a marginal share
        proportional to on-court minute percentage.

        Args:
            on_off: On/off stats row with on/off court ratings and minutes.
            season_stats: Season stats row with games_played.
            team_stats: Dict with 'pts_for', 'pts_against', and 'games'.
            league_pace: League average pace (possessions per 48 min).

        Returns:
            Estimated expected wins attributed to the player, rounded
            to 1 decimal place.
        """
        games = team_stats.get("games", 0)
        if not games or league_pace <= 0:
            return 0.0

        on_off_rtg = safe_float(on_off.on_court_off_rating)
        on_def_rtg = safe_float(on_off.on_court_def_rating)
        off_off_rtg = safe_float(on_off.off_court_off_rating)
        off_def_rtg = safe_float(on_off.off_court_def_rating)

        on_minutes = safe_float(on_off.on_court_minutes)
        off_minutes = safe_float(on_off.off_court_minutes)
        total_minutes = on_minutes + off_minutes

        pct_on_court = safe_div(on_minutes, total_minutes, default=0.5)

        # Convert per-100-possession ratings to per-game points using pace
        pace_factor = league_pace / 100.0

        on_pts_for = on_off_rtg * pace_factor
        on_pts_against = on_def_rtg * pace_factor
        off_pts_for = off_off_rtg * pace_factor
        off_pts_against = off_def_rtg * pace_factor

        # Expected wins with player on court for all games
        full_xwins = self.pythagorean_expected_wins(
            on_pts_for, on_pts_against, games
        )

        # Expected wins with player off court for all games
        zero_xwins = self.pythagorean_expected_wins(
            off_pts_for, off_pts_against, games
        )

        marginal_wins = (full_xwins - zero_xwins) * pct_on_court

        return round(marginal_wins, 1)

    @staticmethod
    def clutch_epa(
        clutch_stats: object,
        league_avg_clutch_ts: float = 0.530,
    ) -> float:
        """Calculate clutch Expected Points Added (EPA) per game.

        Compares actual clutch scoring to the expected scoring if the
        player shot at the league average clutch true shooting percentage
        on the same volume.

        Args:
            clutch_stats: Clutch stats row with per-game scoring and
                shooting attributes.
            league_avg_clutch_ts: League average true shooting percentage
                during clutch time.

        Returns:
            Per-game clutch EPA. Positive means the player scored more
            than expected; negative means fewer. Returns 0.0 if fewer
            than MIN_CLUTCH_GAMES played.
        """
        gp = safe_float(clutch_stats.games_played)
        if gp < MIN_CLUTCH_GAMES:
            return 0.0

        # Per-game values from the model, scale to season totals
        pts_pg = safe_float(clutch_stats.pts)
        fga_pg = safe_float(clutch_stats.fga)
        fta_pg = safe_float(clutch_stats.fta)

        total_pts = pts_pg * gp
        total_fga = fga_pg * gp
        total_fta = fta_pg * gp

        # True shooting attempts
        tsa = total_fga + FTA_TSA_WEIGHT * total_fta
        if tsa <= 0:
            return 0.0

        # Expected points at league average clutch TS%
        expected_pts = tsa * league_avg_clutch_ts * 2.0
        epa = total_pts - expected_pts

        return round(safe_div(epa, gp), 2)

    @staticmethod
    def garbage_time_pts_estimate(
        season_stats: object,
        on_off: object,
    ) -> float:
        """Estimate garbage time points per game.

        Uses a heuristic based on minutes distribution: players with
        fewer minutes per game relative to a full game are assumed to
        have a higher garbage time fraction.

        This is a rough estimate since play-by-play data is not available.

        Args:
            season_stats: Season stats with games_played and total_minutes.
            on_off: On/off stats with on/off court minutes.

        Returns:
            Estimated garbage time points per game.
        """
        gp = safe_float(season_stats.games_played)
        if gp <= 0:
            return 0.0

        total_minutes = safe_float(season_stats.total_minutes)
        mpg = safe_div(total_minutes, gp)

        # Higher MPG players play less garbage time
        garbage_fraction = max(0.0, 0.12 - (mpg / 48.0 * 0.10))

        total_pts = safe_float(season_stats.total_points)
        ppg = safe_div(total_pts, gp)

        return round(ppg * garbage_fraction, 2)

    def calculate_all(
        self,
        on_off: object,
        season_stats: object,
        clutch_stats: object,
        team_stats: dict[str, float | int],
        league_pace: float,
    ) -> dict[str, float]:
        """Calculate all luck-adjusted metrics for a player.

        Args:
            on_off: On/off court stats row.
            season_stats: Aggregated season stats row.
            clutch_stats: Clutch time stats row.
            team_stats: Dict with 'pts_for', 'pts_against', 'games'.
            league_pace: League average pace.

        Returns:
            Dict with keys: x_wins, clutch_epa, clutch_epa_per_game,
            garbage_time_ppg.
        """
        x_wins = self.player_expected_wins(
            on_off, season_stats, team_stats, league_pace
        )

        clutch_epa_per_game = self.clutch_epa(clutch_stats)

        gp = safe_float(clutch_stats.games_played)
        clutch_epa_total = round(clutch_epa_per_game * gp, 1) if gp >= MIN_CLUTCH_GAMES else 0.0

        garbage_ppg = self.garbage_time_pts_estimate(season_stats, on_off)

        return {
            "x_wins": x_wins,
            "clutch_epa": clutch_epa_total,
            "clutch_epa_per_game": clutch_epa_per_game,
            "garbage_time_ppg": garbage_ppg,
        }
