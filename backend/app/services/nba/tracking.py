"""Player tracking (touches, hustle, speed/distance, catch-shoot, drive, etc)."""

from __future__ import annotations

import logging
from decimal import Decimal

from app.services import nba_data as _nd
from app.services.nba.models import PlayerTrackingData
from app.services.redis_cache import CacheKeyPrefix

logger = logging.getLogger(__name__)


class TrackingMixin:
    """Touches, hustle, and per-action tracking fetchers."""

    def get_touch_stats(self, season: str = "2024-25") -> list[dict]:
        """Get touch tracking stats for all players.

        Returns: touches, front_court_touches, time_of_possession,
                 avg_sec_per_touch, avg_drib_per_touch, pts_per_touch

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player touch stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_TOUCH_STATS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for touch stats (season: %s)", season)
                return cached

        logger.info("Cache miss for touch stats (season: %s), fetching from API", season)
        touches = self._request_with_retry(
            _nd.LeagueDashPtStats,
            season=season,
            per_mode_simple="Totals",
            player_or_team="Player",
            pt_measure_type="Possessions",
        )
        result = touches.get_normalized_dict()["LeagueDashPtStats"]

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_hustle_stats(self, season: str = "2024-25") -> list[dict]:
        """Get hustle stats for all players.

        Returns: deflections, contested_shots, charges_drawn,
                 loose_balls_recovered, box_outs

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player hustle stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_HUSTLE_STATS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for hustle stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for hustle stats (season: %s), fetching from API", season
        )
        hustle = self._request_with_retry(
            _nd.LeagueHustleStatsPlayer,
            season=season,
            per_mode_time="Totals",
        )
        result = hustle.get_normalized_dict()["HustleStatsPlayer"]

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def fetch_all_tracking_data(
        self,
        season: str = "2024-25",
    ) -> dict[int, PlayerTrackingData]:
        """Fetch and combine all tracking data for all players.

        This method fetches data from multiple endpoints and combines them
        into PlayerTrackingData objects. It handles errors gracefully and
        logs progress.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            Dict keyed by player_id with aggregated PlayerTrackingData

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        logger.info("Fetching tracking data for season %s...", season)
        print(f"Fetching tracking data for season {season}...")

        # Fetch all data sources with proper error handling
        logger.info("Fetching traditional stats...")
        print("  - Fetching traditional stats...")
        traditional = {p["PLAYER_ID"]: p for p in self.get_traditional_stats(season)}

        logger.info("Fetching touch stats...")
        print("  - Fetching touch stats...")
        touches = {p["PLAYER_ID"]: p for p in self.get_touch_stats(season)}

        logger.info("Fetching hustle stats...")
        print("  - Fetching hustle stats...")
        hustle = {p["PLAYER_ID"]: p for p in self.get_hustle_stats(season)}

        # Combine into PlayerTrackingData objects
        combined: dict[int, PlayerTrackingData] = {}

        for player_id, trad in traditional.items():
            touch = touches.get(player_id, {})
            hust = hustle.get(player_id, {})

            # Skip players with no touch data
            if not touch.get("TOUCHES"):
                continue

            combined[player_id] = PlayerTrackingData(
                player_id=player_id,
                player_name=trad.get("PLAYER_NAME", ""),
                team_abbreviation=trad.get("TEAM_ABBREVIATION", ""),
                # Game info
                games_played=trad.get("GP", 0) or 0,
                # Offensive tracking
                touches=touch.get("TOUCHES", 0) or 0,
                front_court_touches=touch.get("FRONT_CT_TOUCHES", 0) or 0,
                paint_touches=touch.get("PAINT_TOUCHES", 0) or 0,
                post_touches=touch.get("POST_TOUCHES", 0) or 0,
                elbow_touches=touch.get("ELBOW_TOUCHES", 0) or 0,
                time_of_possession=Decimal(str(touch.get("TIME_OF_POSS", 0) or 0)),
                avg_seconds_per_touch=Decimal(
                    str(touch.get("AVG_SEC_PER_TOUCH", 0) or 0)
                ),
                avg_dribbles_per_touch=Decimal(
                    str(touch.get("AVG_DRIB_PER_TOUCH", 0) or 0)
                ),
                points_per_touch=Decimal(str(touch.get("PTS_PER_TOUCH", 0) or 0)),
                # Defensive/Hustle tracking
                deflections=hust.get("DEFLECTIONS", 0) or 0,
                contested_shots_2pt=hust.get("CONTESTED_SHOTS_2PT", 0) or 0,
                contested_shots_3pt=hust.get("CONTESTED_SHOTS_3PT", 0) or 0,
                charges_drawn=hust.get("CHARGES_DRAWN", 0) or 0,
                loose_balls_recovered=hust.get("LOOSE_BALLS_RECOVERED", 0) or 0,
                off_loose_balls_recovered=hust.get("OFF_LOOSE_BALLS_RECOVERED", 0) or 0,
                def_loose_balls_recovered=hust.get("DEF_LOOSE_BALLS_RECOVERED", 0) or 0,
                pct_loose_balls_off=Decimal(
                    str(hust.get("PCT_LOOSE_BALLS_RECOVERED_OFF", 0) or 0)
                ),
                pct_loose_balls_def=Decimal(
                    str(hust.get("PCT_LOOSE_BALLS_RECOVERED_DEF", 0) or 0)
                ),
                box_outs=hust.get("BOX_OUTS", 0) or 0,
                box_outs_off=hust.get("OFF_BOXOUTS", 0) or 0,
                box_outs_def=hust.get("DEF_BOXOUTS", 0) or 0,
                box_out_player_team_rebs=hust.get("BOX_OUT_PLAYER_TEAM_REBS", 0) or 0,
                box_out_player_rebs=hust.get("BOX_OUT_PLAYER_REBS", 0) or 0,
                pct_box_outs_off=Decimal(str(hust.get("PCT_BOX_OUTS_OFF", 0) or 0)),
                pct_box_outs_def=Decimal(str(hust.get("PCT_BOX_OUTS_DEF", 0) or 0)),
                pct_box_outs_team_reb=Decimal(
                    str(hust.get("PCT_BOX_OUTS_TEAM_REB", 0) or 0)
                ),
                pct_box_outs_reb=Decimal(str(hust.get("PCT_BOX_OUTS_REB", 0) or 0)),
                screen_assists=hust.get("SCREEN_ASSISTS", 0) or 0,
                screen_assist_pts=hust.get("SCREEN_AST_PTS", 0) or 0,
                # Traditional stats
                points=trad.get("PTS", 0) or 0,
                assists=trad.get("AST", 0) or 0,
                turnovers=trad.get("TOV", 0) or 0,
                fta=trad.get("FTA", 0) or 0,
                ftm=trad.get("FTM", 0) or 0,
                minutes=Decimal(str(trad.get("MIN", 0) or 0)),
                plus_minus=trad.get("PLUS_MINUS", 0) or 0,
                steals=trad.get("STL", 0) or 0,
                blocks=trad.get("BLK", 0) or 0,
                offensive_rebounds=trad.get("OREB", 0) or 0,
                defensive_rebounds=trad.get("DREB", 0) or 0,
                rebounds=trad.get("REB", 0) or 0,
                fgm=trad.get("FGM", 0) or 0,
                fga=trad.get("FGA", 0) or 0,
                fg3m=trad.get("FG3M", 0) or 0,
                fg3a=trad.get("FG3A", 0) or 0,
            )

        logger.info("Combined data for %d players", len(combined))
        print(f"  - Combined data for {len(combined)} players")
        return combined

    def get_elbow_touch_stats(self, season: str = "2024-25") -> list[dict]:
        """Get elbow touch tracking stats for all players.

        Returns per-game elbow touches plus shooting/passing/turnover efficiency
        on those touches. Useful for identifying high-post hubs and connective
        playmakers.
        """
        return self._get_pt_measure_stats(
            "ElbowTouch", CacheKeyPrefix.NBA_ELBOW_TOUCH, season
        )

    def get_post_touch_stats(self, season: str = "2024-25") -> list[dict]:
        """Get post touch tracking stats for all players.

        Returns per-game post touches plus shooting/passing/turnover efficiency
        on those touches. Useful for evaluating back-to-basket scoring and
        post-up playmaking.
        """
        return self._get_pt_measure_stats(
            "PostTouch", CacheKeyPrefix.NBA_POST_TOUCH, season
        )

    def get_paint_touch_stats(self, season: str = "2024-25") -> list[dict]:
        """Get paint touch tracking stats for all players.

        Returns per-game paint touches plus efficiency on those touches.
        Captures rim pressure, which is strongly correlated with offensive
        gravity and free-throw generation.
        """
        return self._get_pt_measure_stats(
            "PaintTouch", CacheKeyPrefix.NBA_PAINT_TOUCH, season
        )

    def get_speed_distance_stats(self, season: str = "2024-25") -> list[dict]:
        """Get speed and distance tracking stats for all players (per game)."""
        cache_key = f"{CacheKeyPrefix.NBA_TRACKING_DATA.value}:speed_distance:{season}"
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                return cached

        stats = self._request_with_retry(
            _nd.LeagueDashPtStats,
            season=season,
            pt_measure_type="SpeedDistance",
            per_mode_simple="PerGame",
            player_or_team="Player",
        )
        result = stats.get_normalized_dict()["LeagueDashPtStats"]
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_passing_stats(self, season: str = "2024-25") -> list[dict]:
        """Get passing tracking stats for all players (per game)."""
        cache_key = f"{CacheKeyPrefix.NBA_TRACKING_DATA.value}:passing:{season}"
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                return cached

        stats = self._request_with_retry(
            _nd.LeagueDashPtStats,
            season=season,
            pt_measure_type="Passing",
            per_mode_simple="PerGame",
            player_or_team="Player",
        )
        result = stats.get_normalized_dict()["LeagueDashPtStats"]
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_rebounding_tracking_stats(self, season: str = "2024-25") -> list[dict]:
        """Get rebounding tracking stats for all players (per game)."""
        cache_key = f"{CacheKeyPrefix.NBA_TRACKING_DATA.value}:rebounding:{season}"
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                return cached

        stats = self._request_with_retry(
            _nd.LeagueDashPtStats,
            season=season,
            pt_measure_type="Rebounding",
            per_mode_simple="PerGame",
            player_or_team="Player",
        )
        result = stats.get_normalized_dict()["LeagueDashPtStats"]
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_catch_shoot_stats(self, season: str = "2024-25") -> list[dict]:
        """Get catch-and-shoot tracking stats for all players.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player catch-and-shoot stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_CATCH_SHOOT_STATS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for catch-shoot stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for catch-shoot stats (season: %s), fetching from API", season
        )
        stats = self._request_with_retry(
            _nd.LeagueDashPtStats,
            season=season,
            per_mode_simple="PerGame",
            player_or_team="Player",
            pt_measure_type="CatchShoot",
        )
        result = stats.get_normalized_dict()["LeagueDashPtStats"]

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_pullup_stats(self, season: str = "2024-25") -> list[dict]:
        """Get pull-up shooting tracking stats for all players.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player pull-up shooting stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_PULLUP_STATS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for pull-up stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for pull-up stats (season: %s), fetching from API", season
        )
        stats = self._request_with_retry(
            _nd.LeagueDashPtStats,
            season=season,
            per_mode_simple="PerGame",
            player_or_team="Player",
            pt_measure_type="PullUpShot",
        )
        result = stats.get_normalized_dict()["LeagueDashPtStats"]

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_drive_stats(self, season: str = "2024-25") -> list[dict]:
        """Get drive tracking stats for all players.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player drive stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_DRIVE_STATS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for drive stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for drive stats (season: %s), fetching from API", season
        )
        stats = self._request_with_retry(
            _nd.LeagueDashPtStats,
            season=season,
            per_mode_simple="PerGame",
            player_or_team="Player",
            pt_measure_type="Drives",
        )
        result = stats.get_normalized_dict()["LeagueDashPtStats"]

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def get_efficiency_tracking_stats(self, season: str = "2024-25") -> list[dict]:
        """Get efficiency tracking stats (assisted/unassisted FG breakdown).

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player efficiency tracking stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_EFFICIENCY_STATS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info(
                    "Cache hit for efficiency tracking stats (season: %s)", season
                )
                return cached

        logger.info(
            "Cache miss for efficiency tracking stats (season: %s), fetching from API",
            season,
        )
        efficiency = self._request_with_retry(
            _nd.LeagueDashPtStats,
            season=season,
            per_mode_simple="PerGame",
            player_or_team="Player",
            pt_measure_type="Efficiency",
        )
        result = efficiency.get_normalized_dict()["LeagueDashPtStats"]

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result
