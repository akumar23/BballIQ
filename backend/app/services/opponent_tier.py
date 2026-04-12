"""Service for computing player performance by opponent tier.

Classifies NBA players into quality tiers (Elite, Quality, Role, Bench)
based on composite all-in-one metrics, then aggregates defensive matchup
data per tier to evaluate how a player performs against different
calibers of competition.
"""

from typing import Any

from app.services.metrics_utils import safe_div, safe_float

# Relative weight given to each tier for downstream composite scoring
TIER_WEIGHTS: dict[str, float] = {
    "Elite": 1.0,
    "Quality": 0.8,
    "Role": 0.5,
    "Bench": 0.4,
}

# Minimum total minutes for a player to be included in tier ranking
_MIN_MINUTES_FOR_TIER = 500

# Minimum possessions for a single matchup to be counted
_MIN_MATCHUP_POSSESSIONS = 5

# Minimum total possessions against a tier to produce aggregated stats
_MIN_TIER_POSSESSIONS = 20

# Tier rank boundaries (1-indexed, inclusive upper bounds)
_ELITE_UPPER = 30
_QUALITY_UPPER = 100
_ROLE_UPPER = 200


class OpponentTierCalculator:
    """Assigns players to quality tiers and evaluates per-tier defensive performance.

    Tier assignment uses a composite of available all-in-one impact metrics
    (EPM, RPM, LEBRON, DARKO), falling back to BPM when none of those are
    available. Players are sorted descending and bucketed into four tiers
    by rank position.

    Performance aggregation groups a player's defensive matchup data by
    the tier of each offensive opponent, computing DFG% and points per
    possession allowed for each tier bucket.
    """

    def assign_tiers(
        self,
        all_in_one_metrics: dict[int, Any],
        computed_advanced: dict[int, Any],
        season_stats: dict[int, Any],
    ) -> dict[int, str]:
        """Classify every qualifying player into an opponent tier.

        Args:
            all_in_one_metrics: Mapping of player NBA ID to an object with
                ``epm``, ``rpm``, ``lebron``, and ``darko`` attributes
                (each ``Decimal | None``).
            computed_advanced: Mapping of player NBA ID to an object with
                a ``bpm`` attribute (``Decimal | None``).
            season_stats: Mapping of player NBA ID to an object with a
                ``total_minutes`` attribute (``Decimal | None``).

        Returns:
            Dictionary mapping player NBA ID to tier string
            (``"Elite"``, ``"Quality"``, ``"Role"``, or ``"Bench"``).
        """
        # Filter to players meeting the minutes threshold
        qualifying_ids = [
            pid
            for pid, stats in season_stats.items()
            if safe_float(getattr(stats, "total_minutes", None)) >= _MIN_MINUTES_FOR_TIER
        ]

        # Compute a composite score for each qualifying player
        player_scores: list[tuple[int, float]] = []

        for pid in qualifying_ids:
            score = self._composite_score(
                all_in_one_metrics.get(pid),
                computed_advanced.get(pid),
            )
            if score is not None:
                player_scores.append((pid, score))

        # Sort descending by composite score
        player_scores.sort(key=lambda item: item[1], reverse=True)

        # Assign tiers by rank position
        tiers: dict[int, str] = {}
        for rank, (pid, _) in enumerate(player_scores, start=1):
            tiers[pid] = self._tier_for_rank(rank)

        return tiers

    def performance_by_tier(
        self,
        player_id: int,
        matchups: list[Any],
        opponent_tiers: dict[int, str],
    ) -> dict[str, dict[str, float | int] | None]:
        """Aggregate a player's defensive matchup stats by opponent tier.

        Args:
            player_id: NBA ID of the defending player.
            matchups: List of matchup objects, each having ``player_id``,
                ``off_player_nba_id``, ``partial_poss``, ``matchup_fgm``,
                ``matchup_fga``, ``matchup_fg3m``, and ``matchup_ftm``
                attributes (all ``Decimal | None``).
            opponent_tiers: Mapping returned by :meth:`assign_tiers`.

        Returns:
            Dictionary keyed by tier string. Each value is either ``None``
            (insufficient data) or a dict with ``possessions`` (int),
            ``dfg_pct`` (float), and ``ppp_allowed`` (float).
        """
        # Accumulators per tier
        tier_data: dict[str, dict[str, float]] = {
            tier: {"possessions": 0.0, "fgm": 0.0, "fga": 0.0, "points_allowed": 0.0}
            for tier in TIER_WEIGHTS
        }

        for matchup in matchups:
            # Filter to matchups belonging to this player
            if getattr(matchup, "player_id", None) != player_id:
                continue

            poss = safe_float(getattr(matchup, "partial_poss", None))
            if poss < _MIN_MATCHUP_POSSESSIONS:
                continue

            off_nba_id = getattr(matchup, "off_player_nba_id", None)
            if off_nba_id is None:
                continue

            tier = opponent_tiers.get(off_nba_id)
            if tier is None or tier not in tier_data:
                continue

            fgm = safe_float(getattr(matchup, "matchup_fgm", None))
            fga = safe_float(getattr(matchup, "matchup_fga", None))
            fg3m = safe_float(getattr(matchup, "matchup_fg3m", None))
            ftm = safe_float(getattr(matchup, "matchup_ftm", None))

            # Points allowed: each FGM is worth 2 plus bonus for 3-pointers and FTs
            points_allowed = fgm * 2 + fg3m + ftm

            bucket = tier_data[tier]
            bucket["possessions"] += poss
            bucket["fgm"] += fgm
            bucket["fga"] += fga
            bucket["points_allowed"] += points_allowed

        # Build result dict, enforcing minimum possessions per tier
        result: dict[str, dict[str, float | int] | None] = {}

        for tier in TIER_WEIGHTS:
            bucket = tier_data[tier]
            total_poss = bucket["possessions"]

            if total_poss < _MIN_TIER_POSSESSIONS:
                result[tier] = None
                continue

            result[tier] = {
                "possessions": int(total_poss),
                "dfg_pct": round(safe_div(bucket["fgm"], bucket["fga"]), 4),
                "ppp_allowed": round(safe_div(bucket["points_allowed"], total_poss), 4),
            }

        return result

    # ------------------------------------------------------------------
    # Private helpers
    # ------------------------------------------------------------------

    @staticmethod
    def _composite_score(
        aio: Any | None,
        adv: Any | None,
    ) -> float | None:
        """Average all available all-in-one metrics, falling back to BPM.

        Args:
            aio: Object with ``epm``, ``rpm``, ``lebron``, ``darko`` attrs.
            adv: Object with ``bpm`` attribute.

        Returns:
            Composite float score, or ``None`` if nothing is available.
        """
        values: list[float] = []

        if aio is not None:
            for attr in ("epm", "rpm", "lebron", "darko"):
                raw = getattr(aio, attr, None)
                if raw is not None:
                    values.append(safe_float(raw))

        # Fall back to BPM when no all-in-one metrics are present
        if not values and adv is not None:
            bpm = getattr(adv, "bpm", None)
            if bpm is not None:
                values.append(safe_float(bpm))

        if not values:
            return None

        return sum(values) / len(values)

    @staticmethod
    def _tier_for_rank(rank: int) -> str:
        """Map a 1-based rank to a tier label.

        Args:
            rank: Player rank (1 = best).

        Returns:
            One of ``"Elite"``, ``"Quality"``, ``"Role"``, or ``"Bench"``.
        """
        if rank <= _ELITE_UPPER:
            return "Elite"
        if rank <= _QUALITY_UPPER:
            return "Quality"
        if rank <= _ROLE_UPPER:
            return "Role"
        return "Bench"
