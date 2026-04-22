"""Defensive tracking (contested shots, rim/zone defense, matchups, synergy)."""

from __future__ import annotations

import logging
from typing import Any

from app.services import nba_data as _nd
from app.services.redis_cache import CacheKeyPrefix

logger = logging.getLogger(__name__)


class DefenseMixin:
    """Defensive tracking, zone defense, defender-distance, and matchup fetchers."""

    def get_defensive_stats(self, season: str = "2024-25") -> list[dict]:
        """Get defensive tracking stats for all players.

        Returns: dfg%, contested_2pt, contested_3pt

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player defensive stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_DEFENSIVE_STATS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for defensive stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for defensive stats (season: %s), fetching from API", season
        )
        defense = self._request_with_retry(
            _nd.LeagueDashPtDefend,
            season=season,
            per_mode_simple="Totals",
            defense_category="Overall",
        )
        result = defense.get_normalized_dict()["LeagueDashPTDefend"]

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_rim_protection_stats(self, season: str = "2024-25") -> list[dict]:
        """Get rim protection stats for all players.

        Returns defensive stats for shots taken within 6 feet of the basket.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player rim protection stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_RIM_PROTECTION, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for rim protection stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for rim protection stats (season: %s), fetching from API",
            season,
        )
        rim = self._request_with_retry(
            _nd.LeagueDashPtDefend,
            season=season,
            per_mode_simple="Totals",
            defense_category="Less Than 6Ft",
        )
        result = rim.get_normalized_dict()["LeagueDashPTDefend"]

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_three_point_defense_stats(self, season: str = "2024-25") -> list[dict]:
        """Get 3-point defense stats for all players.

        Returns defensive stats for 3-point shots contested by each player.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player 3-point defense stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_DEFENSE_3PT, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info(
                    "Cache hit for 3PT defense stats (season: %s)", season
                )
                return cached

        logger.info(
            "Cache miss for 3PT defense stats (season: %s), fetching from API",
            season,
        )
        three_pt = self._request_with_retry(
            _nd.LeagueDashPtDefend,
            season=season,
            per_mode_simple="Totals",
            defense_category="3 Pointers",
        )
        result = three_pt.get_normalized_dict()["LeagueDashPTDefend"]

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_two_point_defense_stats(self, season: str = "2024-25") -> list[dict]:
        """Get 2-point defense stats for all players.

        Returns defensive stats for 2-point shots contested by each player,
        complementing the existing rim-protection (<6ft) and 3-point coverage.
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_DEFENSE_2PT, season)

        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for 2PT defense stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for 2PT defense stats (season: %s), fetching from API",
            season,
        )
        two_pt = self._request_with_retry(
            _nd.LeagueDashPtDefend,
            season=season,
            per_mode_simple="Totals",
            defense_category="2 Pointers",
        )
        result = two_pt.get_normalized_dict()["LeagueDashPTDefend"]
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_long_midrange_defense_stats(
        self, season: str = "2024-25"
    ) -> list[dict]:
        """Get long-midrange (>15 ft) defense stats for all players."""
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_DEFENSE_LONG_MID, season)

        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info(
                    "Cache hit for long-mid defense stats (season: %s)", season
                )
                return cached

        logger.info(
            "Cache miss for long-mid defense stats (season: %s), fetching from API",
            season,
        )
        long_mid = self._request_with_retry(
            _nd.LeagueDashPtDefend,
            season=season,
            per_mode_simple="Totals",
            defense_category="Greater Than 15Ft",
        )
        result = long_mid.get_normalized_dict()["LeagueDashPTDefend"]
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_less_than_10ft_defense_stats(
        self, season: str = "2024-25"
    ) -> list[dict]:
        """Get <10 ft defense stats for all players (near-rim + short paint)."""
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_DEFENSE_LT_10FT, season)

        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info(
                    "Cache hit for <10ft defense stats (season: %s)", season
                )
                return cached

        logger.info(
            "Cache miss for <10ft defense stats (season: %s), fetching from API",
            season,
        )
        lt_10 = self._request_with_retry(
            _nd.LeagueDashPtDefend,
            season=season,
            per_mode_simple="Totals",
            defense_category="Less Than 10Ft",
        )
        result = lt_10.get_normalized_dict()["LeagueDashPTDefend"]
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_defender_distance_shooting(
        self, season: str = "2024-25", distance_range: str = ""
    ) -> list[dict]:
        """Get shooting stats filtered by closest defender distance.

        Args:
            season: NBA season string
            distance_range: One of "0-2 Feet - Very Tight", "2-4 Feet - Tight",
                          "4-6 Feet - Open", "6+ Feet - Wide Open", or "" for overall
        """
        cache_key = f"{CacheKeyPrefix.NBA_TRACKING_DATA.value}:def_dist:{distance_range}:{season}"
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                return cached

        stats = self._request_with_retry(
            _nd.LeagueDashPlayerPtShot,
            season=season,
            per_mode_simple="PerGame",
            close_def_dist_range_nullable=distance_range,
        )
        result = stats.get_normalized_dict()["LeagueDashPTShots"]
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_defensive_synergy_stats(
        self, play_type: str, season: str = "2024-25"
    ) -> list[dict]:
        """Get defensive Synergy play type stats for all players.

        Args:
            play_type: Play type name (e.g., "Isolation", "PRBallHandler")
            season: NBA season string
        """
        cache_key = f"{CacheKeyPrefix.NBA_PLAY_TYPE_STATS.value}:def:{play_type}:{season}"
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                return cached

        synergy = self._request_with_retry(
            _nd.SynergyPlayTypes,
            season=season,
            season_type_all_star="Regular Season",
            play_type_nullable=play_type,
            player_or_team_abbreviation="P",
            type_grouping_nullable="defensive",
        )
        result = synergy.get_normalized_dict().get("SynergyPlayType", [])
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_matchup_stats(
        self,
        season: str = "2024-25",
        def_player_id: int | None = None,
        off_player_id: int | None = None,
    ) -> list[dict]:
        """Get player-vs-player matchup data from LeagueSeasonMatchups.

        Can filter by defender or offensive player. If neither is specified,
        returns all matchups (very large dataset).

        Args:
            season: NBA season string (e.g., "2024-25")
            def_player_id: Filter by defender NBA player ID
            off_player_id: Filter by offensive player NBA player ID

        Returns:
            List of matchup dictionaries with per-matchup shooting stats

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        # Build a specific cache key based on filters
        suffix = f"{season}"
        if def_player_id:
            suffix += f":def_{def_player_id}"
        if off_player_id:
            suffix += f":off_{off_player_id}"
        cache_key = f"{CacheKeyPrefix.NBA_MATCHUP_STATS.value}:{suffix}"

        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for matchup stats (%s)", suffix)
                return cached

        logger.info(
            "Cache miss for matchup stats (%s), fetching from API", suffix
        )

        kwargs: dict[str, Any] = {
            "season": season,
            "per_mode_simple": "Totals",
            "season_type_playoffs": "Regular Season",
        }
        if def_player_id:
            kwargs["def_player_id_nullable"] = def_player_id
        if off_player_id:
            kwargs["off_player_id_nullable"] = off_player_id

        matchups = self._request_with_retry(_nd.LeagueSeasonMatchups, **kwargs)
        result = matchups.get_normalized_dict()["SeasonMatchups"]

        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_all_matchup_stats(
        self,
        season: str = "2024-25",
        player_ids: list[int] | None = None,
        progress_callback: callable | None = None,
    ) -> dict[int, list[dict]]:
        """Fetch defensive matchup data for multiple players.

        For each player, fetches their top matchups as a defender.

        Args:
            season: NBA season string (e.g., "2024-25")
            player_ids: List of NBA player IDs to fetch matchups for.
                If None, fetches for all players (expensive).
            progress_callback: Optional callback(current, total, player_name)

        Returns:
            Dict keyed by defender player_id with list of matchup dicts
        """
        result: dict[int, list[dict]] = {}

        if player_ids is None:
            logger.warning("No player_ids provided, skipping matchup fetch")
            return result

        for idx, player_id in enumerate(player_ids):
            if progress_callback:
                progress_callback(idx + 1, len(player_ids), str(player_id))

            try:
                matchups = self.get_matchup_stats(
                    season=season, def_player_id=player_id
                )
                # Sort by partial possessions descending to get top matchups
                matchups.sort(
                    key=lambda m: m.get("PARTIAL_POSS", 0) or 0, reverse=True
                )
                result[player_id] = matchups
            except Exception as e:
                logger.warning(
                    "Failed to fetch matchups for player %d: %s", player_id, e
                )
                continue

        logger.info("Fetched matchup data for %d players", len(result))
        return result
