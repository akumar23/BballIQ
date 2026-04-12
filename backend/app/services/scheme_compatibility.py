"""Service for scoring player fit across offensive scheme archetypes.

Evaluates how well a player's statistical profile aligns with five
distinct offensive systems:

1. **Motion/Read** -- Warriors/Spurs ball-movement offense
2. **PnR Heavy** -- Mavericks/Hawks pick-and-roll centric attack
3. **ISO Heavy** -- Thunder/Nets isolation-oriented scheme
4. **Egalitarian** -- Nuggets/Celtics versatile, balanced offense
5. **Post-Up** -- Embiid/Jokic post-centric system

Each archetype method returns a 0-100 fit score. A ``scheme_flexibility``
composite (average of the top three fits) measures overall adaptability.
"""

from typing import Any

from app.services.metrics_utils import normalize_to_0_100, safe_float

# Default PPP percentile when the underlying value is missing
_DEFAULT_PPP_PERCENTILE: float = 50.0


class SchemeCompatibilityCalculator:
    """Score a player's compatibility with five offensive archetypes.

    All ``Decimal`` fields on the input objects are converted through
    :func:`safe_float` before use, and ``None`` values are handled
    gracefully throughout.

    Args:
        play_types: Object with season play-type attributes (PPP,
            percentiles, frequencies) matching
            :class:`~app.models.season_play_type_stats.SeasonPlayTypeStats`.
        advanced: Object with advanced stat attributes matching
            :class:`~app.models.advanced_stats.PlayerAdvancedStats`.
        per75: Object with per-75-possession stats matching
            :class:`~app.models.per_75_stats.Per75Stats`.
        shooting: Object with shooting-tracking attributes matching
            :class:`~app.models.shooting_tracking.PlayerShootingTracking`.
        shot_zones: List of shot-zone objects matching
            :class:`~app.models.shot_zones.PlayerShotZones`.
    """

    def __init__(
        self,
        play_types: Any,
        advanced: Any,
        per75: Any,
        shooting: Any,
        shot_zones: list[Any],
    ) -> None:
        self._pt = play_types
        self._adv = advanced
        self._p75 = per75
        self._shoot = shooting
        self._zones = shot_zones

    # ------------------------------------------------------------------
    # Public API
    # ------------------------------------------------------------------

    def motion_read_fit(self) -> float:
        """Warriors/Spurs motion-read offense fit (0-100).

        Rewards cutting, off-screen play, spot-up shooting, passing,
        screen assists, low usage, and catch-and-shoot efficiency.
        """
        cut_ppp_pctile = self._pctile("cut_ppp_percentile")
        off_screen_pctile = self._pctile("off_screen_ppp_percentile")
        spot_up_pctile = self._pctile("spot_up_ppp_percentile")

        passing_score = normalize_to_0_100(
            safe_float(getattr(self._adv, "ast_ratio", None)),
            5.0,
            30.0,
        )

        screen_assists_per_75 = safe_float(
            getattr(self._p75, "screen_assists_per_75", None)
        )
        screen_assists_score = normalize_to_0_100(screen_assists_per_75, 0.0, 5.0)

        usg_pct = safe_float(getattr(self._adv, "usg_pct", None))
        low_usage_bonus = max(0.0, min(100.0, (30.0 - usg_pct * 100.0) / 12.0 * 100.0))

        catch_shoot_efg = safe_float(
            getattr(self._shoot, "catch_shoot_efg_pct", None)
        )
        catch_shoot_efg_score = normalize_to_0_100(catch_shoot_efg, 0.42, 0.62)

        score = (
            0.20 * cut_ppp_pctile
            + 0.15 * off_screen_pctile
            + 0.15 * spot_up_pctile
            + 0.15 * passing_score
            + 0.10 * screen_assists_score
            + 0.10 * low_usage_bonus
            + 0.15 * catch_shoot_efg_score
        )
        return self._clamp(score)

    def pnr_heavy_fit(self) -> float:
        """Mavericks/Hawks PnR-heavy offense fit (0-100).

        Computes separate handler and roller scores, returns the higher
        of the two.
        """
        handler_freq = safe_float(
            getattr(self._pt, "pnr_ball_handler_freq", None)
        )
        roller_freq = safe_float(
            getattr(self._pt, "pnr_roll_man_freq", None)
        )

        handler_score = self._pnr_handler_score()
        roller_score = self._pnr_roller_score()

        # Use the role with higher frequency as primary, take the max
        if handler_freq >= roller_freq:
            return self._clamp(max(handler_score, roller_score))
        return self._clamp(max(roller_score, handler_score))

    def iso_heavy_fit(self) -> float:
        """Thunder/Nets isolation-heavy offense fit (0-100).

        Rewards isolation efficiency, pull-up shooting, high usage,
        true-shooting efficiency, and driving ability.
        """
        iso_pctile = self._pctile("isolation_ppp_percentile")

        pullup_efg = safe_float(getattr(self._shoot, "pullup_efg_pct", None))
        pullup_efg_score = normalize_to_0_100(pullup_efg, 0.38, 0.58)

        usg_pct = safe_float(getattr(self._adv, "usg_pct", None))
        usg_score = normalize_to_0_100(usg_pct * 100.0, 15.0, 35.0)

        ts_pct = safe_float(getattr(self._adv, "ts_pct", None))
        ts_score = normalize_to_0_100(ts_pct * 100.0, 50.0, 65.0)

        drive_score = self._drive_score()

        score = (
            0.30 * iso_pctile
            + 0.25 * pullup_efg_score
            + 0.20 * usg_score
            + 0.15 * ts_score
            + 0.10 * drive_score
        )
        return self._clamp(score)

    def egalitarian_fit(self) -> float:
        """Nuggets/Celtics egalitarian offense fit (0-100).

        Rewards play-type versatility (multiple play types above 50th
        percentile), true-shooting, assist-to-turnover ratio, spot-up
        shooting, and low turnover rate.
        """
        # Count play types with >= 50th percentile PPP
        play_type_pctile_attrs = [
            "isolation_ppp_percentile",
            "pnr_ball_handler_ppp_percentile",
            "spot_up_ppp_percentile",
            "transition_ppp_percentile",
            "cut_ppp_percentile",
            "off_screen_ppp_percentile",
        ]
        above_50_count = sum(
            1
            for attr in play_type_pctile_attrs
            if self._pctile(attr) >= 50.0
        )
        versatility_bonus = (above_50_count / 6.0) * 100.0

        ts_pct = safe_float(getattr(self._adv, "ts_pct", None))
        ts_score = normalize_to_0_100(ts_pct * 100.0, 50.0, 65.0)

        ast_to = safe_float(getattr(self._adv, "ast_to", None))
        ast_to_score = normalize_to_0_100(ast_to, 1.0, 4.0)

        spot_up_pctile = self._pctile("spot_up_ppp_percentile")

        # Estimate turnover percentage from ast_to ratio
        # tov_pct ~ 100 / ast_to when ast_to > 0 (rough inverse proxy)
        if ast_to > 0:
            tov_pct_est = min(100.0 / ast_to, 30.0)
        else:
            tov_pct_est = 30.0
        low_tov_bonus = max(0.0, min(100.0, (20.0 - tov_pct_est) / 10.0 * 100.0))

        score = (
            0.30 * versatility_bonus
            + 0.20 * ts_score
            + 0.20 * ast_to_score
            + 0.15 * spot_up_pctile
            + 0.15 * low_tov_bonus
        )
        return self._clamp(score)

    def post_up_fit(self) -> float:
        """Embiid/Jokic post-up centric offense fit (0-100).

        Rewards post-up efficiency, restricted-area finishing, passing
        from the post, offensive rebounding, and free-throw drawing.
        """
        post_up_pctile = self._pctile("post_up_ppp_percentile")

        restricted_fg_score = self._restricted_area_fg_score()

        ast_ratio = safe_float(getattr(self._adv, "ast_ratio", None))
        passing_score = normalize_to_0_100(ast_ratio, 5.0, 30.0)

        oreb_per_75 = safe_float(getattr(self._p75, "oreb_per_75", None))
        oreb_score = normalize_to_0_100(oreb_per_75, 0.0, 5.0)

        fta_per_75 = safe_float(getattr(self._p75, "fta_per_75", None))
        fga_per_75 = safe_float(getattr(self._p75, "fga_per_75", None))
        ft_rate = fta_per_75 / fga_per_75 if fga_per_75 > 0 else 0.0
        ft_rate_score = normalize_to_0_100(ft_rate, 0.20, 0.50)

        score = (
            0.35 * post_up_pctile
            + 0.20 * restricted_fg_score
            + 0.20 * passing_score
            + 0.15 * oreb_score
            + 0.10 * ft_rate_score
        )
        return self._clamp(score)

    def calculate_all(self) -> dict[str, float]:
        """Compute all five archetype fits and the flexibility composite.

        Returns:
            Dictionary with keys ``motion_read``, ``pnr_heavy``,
            ``iso_heavy``, ``egalitarian``, ``post_up``, and
            ``scheme_flexibility`` (average of the top three fits).
        """
        fits = {
            "motion_read": self.motion_read_fit(),
            "pnr_heavy": self.pnr_heavy_fit(),
            "iso_heavy": self.iso_heavy_fit(),
            "egalitarian": self.egalitarian_fit(),
            "post_up": self.post_up_fit(),
        }

        # Scheme flexibility = average of the top 3 fit scores
        top_three = sorted(fits.values(), reverse=True)[:3]
        fits["scheme_flexibility"] = round(sum(top_three) / 3.0, 2)

        return fits

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    def _pctile(self, attr: str) -> float:
        """Safely retrieve a PPP percentile from play-type data.

        Args:
            attr: Attribute name on the play-types object.

        Returns:
            Float percentile (0-100), defaulting to 50 when ``None``.
        """
        return safe_float(getattr(self._pt, attr, None), default=_DEFAULT_PPP_PERCENTILE)

    @staticmethod
    def _clamp(value: float) -> float:
        """Clamp a score to the [0, 100] range and round to 2 decimals."""
        return round(max(0.0, min(100.0, value)), 2)

    def _drive_score(self) -> float:
        """Normalize drive frequency into a 0-100 score."""
        drives = safe_float(getattr(self._shoot, "drives", None))
        return normalize_to_0_100(drives, 2.0, 15.0)

    def _restricted_area_fg_score(self) -> float:
        """Extract restricted-area FG% from shot zones and normalize.

        Searches ``shot_zones`` for the zone whose name contains
        ``"restricted"`` (case-insensitive) and normalizes its FG%.

        Returns:
            Score 0-100 based on restricted-area FG%, or 50 if not found.
        """
        for zone in self._zones:
            zone_name = getattr(zone, "zone", "") or ""
            if "restricted" in zone_name.lower():
                fg_pct = safe_float(getattr(zone, "fg_pct", None))
                return normalize_to_0_100(fg_pct, 0.50, 0.75)
        return 50.0

    def _pnr_handler_score(self) -> float:
        """Compute PnR ball-handler fit score."""
        pnr_bh_pctile = self._pctile("pnr_ball_handler_ppp_percentile")
        drive_score = self._drive_score()

        pullup_efg = safe_float(getattr(self._shoot, "pullup_efg_pct", None))
        pullup_score = normalize_to_0_100(pullup_efg, 0.38, 0.58)

        ast_ratio = safe_float(getattr(self._adv, "ast_ratio", None))
        playmaking_score = normalize_to_0_100(ast_ratio, 5.0, 30.0)

        fta_per_75 = safe_float(getattr(self._p75, "fta_per_75", None))
        ft_draw_score = normalize_to_0_100(fta_per_75, 1.0, 8.0)

        return (
            0.30 * pnr_bh_pctile
            + 0.20 * drive_score
            + 0.15 * pullup_score
            + 0.20 * playmaking_score
            + 0.15 * ft_draw_score
        )

    def _pnr_roller_score(self) -> float:
        """Compute PnR roll-man fit score."""
        pnr_rm_pctile = self._pctile("pnr_roll_man_ppp_percentile")
        restricted_fg_score = self._restricted_area_fg_score()

        screen_assists_per_75 = safe_float(
            getattr(self._p75, "screen_assists_per_75", None)
        )
        screen_ast_score = normalize_to_0_100(screen_assists_per_75, 0.0, 5.0)

        cut_ppp_pctile = self._pctile("cut_ppp_percentile")

        return (
            0.30 * pnr_rm_pctile
            + 0.25 * restricted_fg_score
            + 0.25 * screen_ast_score
            + 0.20 * cut_ppp_pctile
        )
