"""Service for fetching data from NBA API and PBP Stats.

This module provides rate-limited, resilient access to the NBA Stats API
with exponential backoff, retry logic, circuit breaker protection, and
Redis caching to minimize external API calls.
"""

from __future__ import annotations

import logging
import time
from dataclasses import dataclass
from decimal import Decimal
from typing import Any, Optional, TypeVar

from nba_api.stats.endpoints import (
    CommonAllPlayers,
    LeagueDashPlayerStats,
)
from nba_api.stats.endpoints.leaguedashteamstats import LeagueDashTeamStats
from nba_api.stats.endpoints.playercareerstats import PlayerCareerStats
from nba_api.stats.endpoints.leaguedashlineups import LeagueDashLineups
from nba_api.stats.endpoints.leaguedashplayerclutch import LeagueDashPlayerClutch
from nba_api.stats.endpoints.leaguedashplayershotlocations import (
    LeagueDashPlayerShotLocations,
)
from nba_api.stats.endpoints.leaguedashptdefend import LeagueDashPtDefend
from nba_api.stats.endpoints.leaguedashptstats import LeagueDashPtStats
from nba_api.stats.endpoints.leaguehustlestatsplayer import LeagueHustleStatsPlayer
from nba_api.stats.endpoints.shotchartleaguewide import ShotChartLeagueWide
from nba_api.stats.endpoints.synergyplaytypes import SynergyPlayTypes
from nba_api.stats.endpoints.leagueseasonmatchups import LeagueSeasonMatchups
from nba_api.stats.endpoints.teamplayeronoffsummary import TeamPlayerOnOffSummary
from nba_api.stats.static import teams as nba_teams

from app.core.config import settings
from app.services.rate_limiter import (
    CircuitBreakerError,
    RateLimitError,
    calculate_backoff_delay,
    get_nba_session,
    nba_api_circuit_breaker,
    with_retry,
)
from app.services.redis_cache import (
    CacheKeyPrefix,
    redis_cache,
)


logger = logging.getLogger(__name__)

# Type variable for endpoint classes
EndpointT = TypeVar("EndpointT")


@dataclass
class PlayerOnOffData:
    """On/Off court data for a player."""

    player_id: int
    player_name: str
    team_id: int
    team_abbreviation: str

    # On-court stats
    on_court_min: Decimal
    on_court_plus_minus: Decimal
    on_court_off_rating: Decimal
    on_court_def_rating: Decimal
    on_court_net_rating: Decimal

    # Off-court stats
    off_court_min: Decimal
    off_court_plus_minus: Decimal
    off_court_off_rating: Decimal
    off_court_def_rating: Decimal
    off_court_net_rating: Decimal

    # Differentials (on - off)
    plus_minus_diff: Decimal
    off_rating_diff: Decimal
    def_rating_diff: Decimal
    net_rating_diff: Decimal


@dataclass
class LineupData:
    """5-man lineup data."""

    lineup_id: str  # Sorted player IDs joined
    player_ids: list[int]
    player_names: list[str]
    team_id: int
    team_abbreviation: str

    # Lineup stats
    games_played: int
    minutes: Decimal
    plus_minus: Decimal
    off_rating: Decimal
    def_rating: Decimal
    net_rating: Decimal


@dataclass
class PlayTypeMetrics:
    """Metrics for a single play type."""

    possessions: int
    points: int
    fgm: int
    fga: int
    fg3m: int | None = None  # Only for spot-up
    fg3a: int | None = None  # Only for spot-up


@dataclass
class PlayerPlayTypeData:
    """Play type data for a single player."""

    player_id: int
    player_name: str
    team_abbreviation: str

    isolation: PlayTypeMetrics | None = None
    pnr_ball_handler: PlayTypeMetrics | None = None
    pnr_roll_man: PlayTypeMetrics | None = None
    post_up: PlayTypeMetrics | None = None
    spot_up: PlayTypeMetrics | None = None
    transition: PlayTypeMetrics | None = None
    cut: PlayTypeMetrics | None = None
    off_screen: PlayTypeMetrics | None = None

    # Total possessions across all play types
    total_poss: int = 0


# Play type name mappings for NBA API
PLAY_TYPE_MAPPING = {
    "isolation": "Isolation",
    "pnr_ball_handler": "PRBallHandler",
    "pnr_roll_man": "PRRollman",
    "post_up": "Postup",
    "spot_up": "Spotup",
    "transition": "Transition",
    "cut": "Cut",
    "off_screen": "OffScreen",
}

# Key defensive play types for defensive synergy data
DEFENSIVE_PLAY_TYPE_MAPPING = {
    "isolation": "Isolation",
    "pnr_ball_handler": "PRBallHandler",
    "post_up": "Postup",
    "spot_up": "Spotup",
    "transition": "Transition",
}


@dataclass
class DefensivePlayTypeMetrics:
    """Metrics for a single defensive play type."""

    possessions: int
    points: int
    fgm: int
    fga: int
    ppp: Decimal  # Points per possession
    fg_pct: Decimal
    percentile: Decimal


@dataclass
class PlayerDefensivePlayTypeData:
    """Defensive play type data for a single player."""

    player_id: int
    player_name: str
    team_abbreviation: str

    isolation: DefensivePlayTypeMetrics | None = None
    pnr_ball_handler: DefensivePlayTypeMetrics | None = None
    post_up: DefensivePlayTypeMetrics | None = None
    spot_up: DefensivePlayTypeMetrics | None = None
    transition: DefensivePlayTypeMetrics | None = None

    # Total possessions across all defensive play types
    total_poss: int = 0


@dataclass
class PlayerTrackingData:
    """Aggregated tracking data for a player."""

    player_id: int
    player_name: str
    team_abbreviation: str

    # Game info
    games_played: int

    # Offensive tracking
    touches: int
    front_court_touches: int
    time_of_possession: Decimal
    avg_seconds_per_touch: Decimal
    avg_dribbles_per_touch: Decimal
    points_per_touch: Decimal

    # Defensive/Hustle tracking
    deflections: int
    contested_shots_2pt: int
    contested_shots_3pt: int
    charges_drawn: int
    loose_balls_recovered: int
    box_outs: int
    box_outs_off: int
    box_outs_def: int
    screen_assists: int
    screen_assist_pts: int

    # Traditional stats for calculations
    points: int
    assists: int
    turnovers: int
    steals: int
    blocks: int
    offensive_rebounds: int
    defensive_rebounds: int
    rebounds: int
    fgm: int
    fga: int
    fg3m: int
    fg3a: int
    ftm: int
    fta: int
    ftm: int
    minutes: Decimal
    games_played: int
    rebounds: int
    plus_minus: int


class NBADataService:
    """Fetches tracking and traditional stats from NBA API.

    This service implements robust rate limiting with:
    - Exponential backoff with jitter for retries
    - Circuit breaker to prevent hammering a failing API
    - Configurable retry logic
    - Proper HTTP headers for NBA API authentication
    - Redis caching to minimize external API calls

    Attributes:
        cache_dir: Directory for caching API responses
        max_retries: Maximum retry attempts per request
        base_delay: Base delay between requests in seconds
        bypass_cache: If True, skip cache lookup and force API fetch
    """

    def __init__(
        self,
        max_retries: int | None = None,
        base_delay: float | None = None,
        bypass_cache: bool = False,
    ):
        """Initialize the NBA Data Service.

        Args:
            max_retries: Maximum retry attempts (uses config default if None)
            base_delay: Base delay between requests (uses config default if None)
            bypass_cache: If True, skip Redis cache and always fetch from API
        """
        self.cache_dir = settings.nba_api_cache_dir
        self.max_retries = (
            max_retries if max_retries is not None else settings.nba_api_max_retries
        )
        self.base_delay = (
            base_delay if base_delay is not None else settings.nba_api_base_delay
        )
        self.bypass_cache = bypass_cache
        self._session = get_nba_session()

    def _request_with_retry(
        self,
        endpoint_class: type[EndpointT],
        **kwargs: Any,
    ) -> EndpointT:
        """Make API request with retry logic and proper headers.

        This method wraps NBA API endpoint calls with:
        - Circuit breaker protection
        - Exponential backoff on failures
        - Proper HTTP headers via custom session
        - Comprehensive logging

        Args:
            endpoint_class: The NBA API endpoint class to instantiate
            **kwargs: Arguments to pass to the endpoint

        Returns:
            Instantiated endpoint with data

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
            Exception: For non-retryable errors
        """
        # Check circuit breaker before attempting
        if not nba_api_circuit_breaker.can_execute():
            recovery_time = self._get_circuit_recovery_time()
            raise CircuitBreakerError(
                f"NBA API circuit breaker is open. Recovery in {recovery_time:.1f}s",
                recovery_time,
            )

        last_exception: Exception | None = None

        for attempt in range(self.max_retries + 1):
            try:
                # Apply delay (base delay for first request, backoff for retries)
                if attempt > 0:
                    delay = calculate_backoff_delay(
                        attempt - 1, base_delay=self.base_delay
                    )
                    endpoint_name = getattr(endpoint_class, "__name__", str(endpoint_class))
                    logger.info(
                        "Retry attempt %d/%d for %s, waiting %.2fs",
                        attempt,
                        self.max_retries,
                        endpoint_name,
                        delay,
                    )
                else:
                    delay = self.base_delay

                time.sleep(delay)

                # Make the API call
                # Note: We don't pass custom headers - the nba_api library
                # has well-configured defaults (STATS_HEADERS) that work better
                # Passing custom headers can cause timeout issues
                endpoint = endpoint_class(
                    **kwargs,
                    timeout=settings.nba_api_timeout,
                )

                # Record success
                nba_api_circuit_breaker.record_success()
                endpoint_name = getattr(endpoint_class, "__name__", str(endpoint_class))
                logger.debug(
                    "Successfully fetched %s",
                    endpoint_name,
                )

                return endpoint

            except Exception as e:
                last_exception = e
                error_str = str(e).lower()

                # Check if rate limited (429)
                is_rate_limit = any(
                    indicator in error_str
                    for indicator in ["429", "too many requests", "rate limit"]
                )

                # Check if server error (5xx)
                is_server_error = any(
                    str(code) in str(e) for code in [500, 502, 503, 504]
                )

                # Check if timeout error (should retry)
                is_timeout = any(
                    indicator in error_str
                    for indicator in ["timeout", "timed out", "read timed out"]
                )

                # Check if connection error (should retry)
                is_connection_error = any(
                    indicator in error_str
                    for indicator in [
                        "connection reset",
                        "connection aborted",
                        "connection refused",
                        "broken pipe",
                        "connectionreseterror",
                    ]
                )

                endpoint_name = getattr(endpoint_class, "__name__", str(endpoint_class))
                if is_rate_limit or is_server_error or is_timeout or is_connection_error:
                    logger.warning(
                        "Request to %s failed (attempt %d/%d): %s",
                        endpoint_name,
                        attempt + 1,
                        self.max_retries + 1,
                        e,
                    )
                    nba_api_circuit_breaker.record_failure()
                    continue
                else:
                    # Non-retryable error
                    logger.error(
                        "Non-retryable error for %s: %s",
                        endpoint_name,
                        e,
                    )
                    nba_api_circuit_breaker.record_failure()
                    raise

        # Max retries exceeded
        nba_api_circuit_breaker.record_failure()

        if last_exception:
            if "429" in str(last_exception) or "rate limit" in str(last_exception).lower():
                raise RateLimitError(
                    f"Rate limited after {self.max_retries + 1} attempts: {last_exception}",
                    retry_after=calculate_backoff_delay(self.max_retries),
                )
            raise last_exception

        raise RuntimeError("Unknown error during retry")

    def _get_circuit_recovery_time(self) -> float:
        """Calculate remaining recovery time for circuit breaker."""
        if nba_api_circuit_breaker._last_failure_time:
            elapsed = time.time() - nba_api_circuit_breaker._last_failure_time
            return max(0, nba_api_circuit_breaker.recovery_timeout - elapsed)
        return 0

    def _get_cache_key(self, prefix: CacheKeyPrefix, season: str) -> str:
        """Build a cache key for the given data type and season.

        Args:
            prefix: Cache key prefix
            season: NBA season string

        Returns:
            Formatted cache key
        """
        return f"{prefix.value}:{season}"

    def get_all_players(self, season: str = "2024-25") -> list[dict]:
        """Get all active players for a season.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player dictionaries with player info

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_PLAYERS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for players (season: %s)", season)
                return cached

        logger.info("Cache miss for players (season: %s), fetching from API", season)
        players = self._request_with_retry(
            CommonAllPlayers,
            is_only_current_season=1,
            season=season,
        )
        result = players.get_normalized_dict()["CommonAllPlayers"]

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_players)
        return result

    def get_traditional_stats(self, season: str = "2024-25") -> list[dict]:
        """Get traditional box score stats for all players.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_TRADITIONAL_STATS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for traditional stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for traditional stats (season: %s), fetching from API", season
        )
        stats = self._request_with_retry(
            LeagueDashPlayerStats,
            season=season,
            per_mode_detailed="Totals",
            measure_type_detailed_defense="Base",
        )
        result = stats.get_normalized_dict()["LeagueDashPlayerStats"]

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
        return result

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
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for touch stats (season: %s)", season)
                return cached

        logger.info("Cache miss for touch stats (season: %s), fetching from API", season)
        touches = self._request_with_retry(
            LeagueDashPtStats,
            season=season,
            per_mode_simple="Totals",
            player_or_team="Player",
            pt_measure_type="Possessions",
        )
        result = touches.get_normalized_dict()["LeagueDashPtStats"]

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
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
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for hustle stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for hustle stats (season: %s), fetching from API", season
        )
        hustle = self._request_with_retry(
            LeagueHustleStatsPlayer,
            season=season,
            per_mode_time="Totals",
        )
        result = hustle.get_normalized_dict()["HustleStatsPlayer"]

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
        return result

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
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for defensive stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for defensive stats (season: %s), fetching from API", season
        )
        defense = self._request_with_retry(
            LeagueDashPtDefend,
            season=season,
            per_mode_simple="Totals",
            defense_category="Overall",
        )
        result = defense.get_normalized_dict()["LeagueDashPTDefend"]

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
        return result

    def get_lineup_stats(self, season: str = "2024-25") -> list[dict]:
        """Get 5-man lineup stats for all teams.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of lineup stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_LINEUP_STATS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for lineup stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for lineup stats (season: %s), fetching from API", season
        )
        lineups = self._request_with_retry(
            LeagueDashLineups,
            season=season,
            per_mode_detailed="Totals",
            measure_type_detailed_defense="Base",
            group_quantity=5,  # 5-man lineups
        )
        result = lineups.get_normalized_dict()["Lineups"]

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
        return result

    def get_on_off_stats_for_team(
        self, team_id: int, season: str = "2024-25"
    ) -> tuple[list[dict], list[dict]]:
        """Get on/off stats for a single team.

        Args:
            team_id: NBA team ID
            season: NBA season string

        Returns:
            Tuple of (on_court_stats, off_court_stats)
        """
        data = self._request_with_retry(
            TeamPlayerOnOffSummary,
            team_id=team_id,
            season=season,
            per_mode_detailed="PerGame",
            measure_type_detailed_defense="Base",
        )
        result = data.get_normalized_dict()
        on_court = result.get("PlayersOnCourtTeamPlayerOnOffSummary", [])
        off_court = result.get("PlayersOffCourtTeamPlayerOnOffSummary", [])
        return on_court, off_court

    def get_all_on_off_stats(
        self,
        season: str = "2024-25",
        progress_callback: Optional[callable] = None,
    ) -> dict[int, PlayerOnOffData]:
        """Get on/off stats for all players across all teams.

        This method iterates through all 30 NBA teams to collect
        on/off data for every player.

        Args:
            season: NBA season string
            progress_callback: Optional callback(team_idx, total_teams, team_name)

        Returns:
            Dict keyed by player_id with PlayerOnOffData
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_ON_OFF_STATS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for on/off stats (season: %s)", season)
                # Convert cached dict back to PlayerOnOffData objects
                return {
                    int(k): PlayerOnOffData(
                        player_id=v["player_id"],
                        player_name=v["player_name"],
                        team_id=v["team_id"],
                        team_abbreviation=v["team_abbreviation"],
                        on_court_min=Decimal(str(v["on_court_min"])),
                        on_court_plus_minus=Decimal(str(v["on_court_plus_minus"])),
                        on_court_off_rating=Decimal(str(v["on_court_off_rating"])),
                        on_court_def_rating=Decimal(str(v["on_court_def_rating"])),
                        on_court_net_rating=Decimal(str(v["on_court_net_rating"])),
                        off_court_min=Decimal(str(v["off_court_min"])),
                        off_court_plus_minus=Decimal(str(v["off_court_plus_minus"])),
                        off_court_off_rating=Decimal(str(v["off_court_off_rating"])),
                        off_court_def_rating=Decimal(str(v["off_court_def_rating"])),
                        off_court_net_rating=Decimal(str(v["off_court_net_rating"])),
                        plus_minus_diff=Decimal(str(v["plus_minus_diff"])),
                        off_rating_diff=Decimal(str(v["off_rating_diff"])),
                        def_rating_diff=Decimal(str(v["def_rating_diff"])),
                        net_rating_diff=Decimal(str(v["net_rating_diff"])),
                    )
                    for k, v in cached.items()
                }

        logger.info(
            "Cache miss for on/off stats (season: %s), fetching from API", season
        )

        all_teams = nba_teams.get_teams()
        combined: dict[int, PlayerOnOffData] = {}

        for idx, team in enumerate(all_teams):
            team_id = team["id"]
            team_abbr = team["abbreviation"]
            team_name = team["full_name"]

            if progress_callback:
                progress_callback(idx + 1, len(all_teams), team_name)

            logger.info("Fetching on/off stats for %s (%d/%d)", team_abbr, idx + 1, len(all_teams))

            try:
                on_court, off_court = self.get_on_off_stats_for_team(team_id, season)

                # Create lookup for off-court data
                off_court_by_player = {p["VS_PLAYER_ID"]: p for p in off_court}

                for player in on_court:
                    player_id = player["VS_PLAYER_ID"]
                    off_data = off_court_by_player.get(player_id, {})

                    on_min = Decimal(str(player.get("MIN", 0) or 0))
                    on_pm = Decimal(str(player.get("PLUS_MINUS", 0) or 0))
                    on_off_rtg = Decimal(str(player.get("OFF_RATING", 0) or 0))
                    on_def_rtg = Decimal(str(player.get("DEF_RATING", 0) or 0))
                    on_net_rtg = Decimal(str(player.get("NET_RATING", 0) or 0))

                    off_min = Decimal(str(off_data.get("MIN", 0) or 0))
                    off_pm = Decimal(str(off_data.get("PLUS_MINUS", 0) or 0))
                    off_off_rtg = Decimal(str(off_data.get("OFF_RATING", 0) or 0))
                    off_def_rtg = Decimal(str(off_data.get("DEF_RATING", 0) or 0))
                    off_net_rtg = Decimal(str(off_data.get("NET_RATING", 0) or 0))

                    combined[player_id] = PlayerOnOffData(
                        player_id=player_id,
                        player_name=player.get("VS_PLAYER_NAME", ""),
                        team_id=team_id,
                        team_abbreviation=team_abbr,
                        on_court_min=on_min,
                        on_court_plus_minus=on_pm,
                        on_court_off_rating=on_off_rtg,
                        on_court_def_rating=on_def_rtg,
                        on_court_net_rating=on_net_rtg,
                        off_court_min=off_min,
                        off_court_plus_minus=off_pm,
                        off_court_off_rating=off_off_rtg,
                        off_court_def_rating=off_def_rtg,
                        off_court_net_rating=off_net_rtg,
                        plus_minus_diff=on_pm - off_pm,
                        off_rating_diff=on_off_rtg - off_off_rtg,
                        def_rating_diff=on_def_rtg - off_def_rtg,
                        net_rating_diff=on_net_rtg - off_net_rtg,
                    )

            except Exception as e:
                logger.warning("Failed to fetch on/off stats for %s: %s", team_abbr, e)
                continue

        logger.info("Collected on/off data for %d players", len(combined))

        # Cache the result (convert dataclasses to dicts for JSON serialization)
        cache_data = {
            str(k): {
                "player_id": v.player_id,
                "player_name": v.player_name,
                "team_id": v.team_id,
                "team_abbreviation": v.team_abbreviation,
                "on_court_min": str(v.on_court_min),
                "on_court_plus_minus": str(v.on_court_plus_minus),
                "on_court_off_rating": str(v.on_court_off_rating),
                "on_court_def_rating": str(v.on_court_def_rating),
                "on_court_net_rating": str(v.on_court_net_rating),
                "off_court_min": str(v.off_court_min),
                "off_court_plus_minus": str(v.off_court_plus_minus),
                "off_court_off_rating": str(v.off_court_off_rating),
                "off_court_def_rating": str(v.off_court_def_rating),
                "off_court_net_rating": str(v.off_court_net_rating),
                "plus_minus_diff": str(v.plus_minus_diff),
                "off_rating_diff": str(v.off_rating_diff),
                "def_rating_diff": str(v.def_rating_diff),
                "net_rating_diff": str(v.net_rating_diff),
            }
            for k, v in combined.items()
        }
        redis_cache.set(cache_key, cache_data, ttl=settings.cache_ttl_tracking_stats)

        return combined

    def fetch_lineup_data(self, season: str = "2024-25") -> list[LineupData]:
        """Fetch and parse lineup data into LineupData objects.

        Args:
            season: NBA season string

        Returns:
            List of LineupData objects
        """
        raw_lineups = self.get_lineup_stats(season)
        lineups: list[LineupData] = []

        for lineup in raw_lineups:
            # Parse GROUP_ID which contains player IDs
            group_id = lineup.get("GROUP_ID", "")
            # GROUP_ID format is typically "PLAYER_ID1 - PLAYER_ID2 - ..."
            player_ids_str = group_id.replace(" ", "").split("-")
            try:
                player_ids = [int(pid) for pid in player_ids_str if pid]
            except ValueError:
                continue

            # GROUP_NAME contains player names
            group_name = lineup.get("GROUP_NAME") or ""
            player_names = [n.strip() for n in group_name.split("-")]

            lineups.append(
                LineupData(
                    lineup_id="-".join(str(p) for p in sorted(player_ids)),
                    player_ids=player_ids,
                    player_names=player_names,
                    team_id=lineup.get("TEAM_ID", 0),
                    team_abbreviation=lineup.get("TEAM_ABBREVIATION", ""),
                    games_played=lineup.get("GP", 0) or 0,
                    minutes=Decimal(str(lineup.get("MIN", 0) or 0)),
                    plus_minus=Decimal(str(lineup.get("PLUS_MINUS", 0) or 0)),
                    off_rating=Decimal(str(lineup.get("OFF_RATING", 0) or 0)),
                    def_rating=Decimal(str(lineup.get("DEF_RATING", 0) or 0)),
                    net_rating=Decimal(str(lineup.get("NET_RATING", 0) or 0)),
                )
            )

        return lineups

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

        logger.info("Fetching defensive stats...")
        print("  - Fetching defensive stats...")
        defense = {p["CLOSE_DEF_PERSON_ID"]: p for p in self.get_defensive_stats(season)}

        # Combine into PlayerTrackingData objects
        combined: dict[int, PlayerTrackingData] = {}

        for player_id, trad in traditional.items():
            touch = touches.get(player_id, {})
            hust = hustle.get(player_id, {})
            defn = defense.get(player_id, {})

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
                box_outs=hust.get("BOX_OUTS", 0) or 0,
                box_outs_off=hust.get("OFF_BOXOUTS", 0) or 0,
                box_outs_def=hust.get("DEF_BOXOUTS", 0) or 0,
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

    def get_synergy_play_type_stats(
        self,
        play_type: str,
        season: str = "2024-25",
        season_type: str = "Regular Season",
    ) -> list[dict]:
        """Get synergy play type stats for all players.

        Args:
            play_type: Play type name (e.g., "Isolation", "PRBallHandler")
            season: NBA season string (e.g., "2024-25")
            season_type: "Regular Season" or "Playoffs"

        Returns:
            List of player play type stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = f"{CacheKeyPrefix.NBA_PLAY_TYPE_STATS.value}:{play_type}:{season}"

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info(
                    "Cache hit for play type stats (type: %s, season: %s)",
                    play_type,
                    season,
                )
                return cached

        logger.info(
            "Cache miss for play type stats (type: %s, season: %s), fetching from API",
            play_type,
            season,
        )

        synergy = self._request_with_retry(
            SynergyPlayTypes,
            season=season,
            season_type_all_star=season_type,
            play_type_nullable=play_type,
            player_or_team_abbreviation="P",  # Player stats
            type_grouping_nullable="offensive",  # Offensive play types
        )
        result = synergy.get_normalized_dict().get("SynergyPlayType", [])

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
        return result

    def fetch_all_play_type_data(
        self,
        season: str = "2024-25",
        progress_callback: Optional[callable] = None,
    ) -> dict[int, PlayerPlayTypeData]:
        """Fetch and combine play type data for all players.

        This method fetches synergy play type stats for all 8 play types
        and combines them into PlayerPlayTypeData objects.

        Args:
            season: NBA season string (e.g., "2024-25")
            progress_callback: Optional callback(play_type_idx, total, play_type_name)

        Returns:
            Dict keyed by player_id with aggregated PlayerPlayTypeData

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        logger.info("Fetching play type data for season %s...", season)
        print(f"Fetching play type data for season {season}...")

        combined: dict[int, PlayerPlayTypeData] = {}
        play_types = list(PLAY_TYPE_MAPPING.items())

        for idx, (field_name, api_name) in enumerate(play_types):
            if progress_callback:
                progress_callback(idx + 1, len(play_types), api_name)

            logger.info("Fetching %s stats (%d/%d)...", api_name, idx + 1, len(play_types))
            print(f"  - Fetching {api_name} stats ({idx + 1}/{len(play_types)})...")

            try:
                play_type_data = self.get_synergy_play_type_stats(api_name, season)

                for player in play_type_data:
                    player_id = player.get("PLAYER_ID")
                    if not player_id:
                        continue

                    # Create or get existing player data
                    if player_id not in combined:
                        combined[player_id] = PlayerPlayTypeData(
                            player_id=player_id,
                            player_name=player.get("PLAYER_NAME", ""),
                            team_abbreviation=player.get("TEAM_ABBREVIATION", ""),
                        )

                    # Create metrics for this play type
                    poss = player.get("POSS", 0) or 0
                    pts = player.get("PTS", 0) or 0
                    fgm = player.get("FGM", 0) or 0
                    fga = player.get("FGA", 0) or 0

                    metrics = PlayTypeMetrics(
                        possessions=poss,
                        points=pts,
                        fgm=fgm,
                        fga=fga,
                    )

                    # For spot-up, also track 3-pointers if available
                    if field_name == "spot_up":
                        metrics.fg3m = player.get("FG3M", 0) or 0
                        metrics.fg3a = player.get("FG3A", 0) or 0

                    # Set the metrics on the player data
                    setattr(combined[player_id], field_name, metrics)

                    # Update total possessions
                    combined[player_id].total_poss += poss

            except Exception as e:
                logger.warning("Failed to fetch %s stats: %s", api_name, e)
                print(f"    Warning: Failed to fetch {api_name} stats: {e}")
                continue

        logger.info("Combined play type data for %d players", len(combined))
        print(f"  - Combined play type data for {len(combined)} players")
        return combined

    def get_advanced_stats(self, season: str = "2024-25") -> list[dict]:
        """Get advanced stats for all players.

        Returns: TS%, USG%, ORtg, DRtg, PACE, PIE, EFG%, AST%, AST_TO,
                 AST_RATIO, OREB%, DREB%, REB%, TM_TOV%

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player advanced stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_ADVANCED_STATS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for advanced stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for advanced stats (season: %s), fetching from API", season
        )
        stats = self._request_with_retry(
            LeagueDashPlayerStats,
            season=season,
            per_mode_detailed="PerGame",
            measure_type_detailed_defense="Advanced",
        )
        result = stats.get_normalized_dict()["LeagueDashPlayerStats"]

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
        return result

    def get_shot_location_stats(self, season: str = "2024-25") -> list[dict]:
        """Get shot location stats (by zone) for all players.

        Returns per-zone FGM, FGA, FG_PCT for: Restricted Area, In The Paint
        (Non-RA), Mid-Range, Left Corner 3, Right Corner 3, Above the Break 3,
        Backcourt.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player shot location stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_SHOT_LOCATIONS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for shot location stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for shot location stats (season: %s), fetching from API",
            season,
        )
        shots = self._request_with_retry(
            LeagueDashPlayerShotLocations,
            season=season,
            distance_range="By Zone",
            per_mode_detailed="PerGame",
        )
        # get_normalized_dict() fails when the API returns nested column headers
        # (unhashable type: 'dict'). Use get_data_frames() which is more robust.
        try:
            dfs = shots.get_data_frames()
            result = dfs[0].to_dict("records") if dfs else []
        except Exception:
            result = shots.get_normalized_dict().get("ShotLocations", [])

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
        return result

    def get_league_shot_averages(self, season: str = "2024-25") -> list[dict]:
        """Get league-wide average FG% by shot zone.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of league shot average dictionaries by zone

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(
            CacheKeyPrefix.NBA_LEAGUE_SHOT_AVERAGES, season
        )

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info(
                    "Cache hit for league shot averages (season: %s)", season
                )
                return cached

        logger.info(
            "Cache miss for league shot averages (season: %s), fetching from API",
            season,
        )
        averages = self._request_with_retry(
            ShotChartLeagueWide,
            season=season,
        )
        result = averages.get_normalized_dict().get("LeagueWide", [])

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
        return result

    def get_clutch_stats(self, season: str = "2024-25") -> list[dict]:
        """Get clutch time stats for all players.

        Clutch is defined as the last 5 minutes of a game when the score
        differential is 5 points or fewer.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player clutch stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_CLUTCH_STATS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for clutch stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for clutch stats (season: %s), fetching from API", season
        )
        clutch = self._request_with_retry(
            LeagueDashPlayerClutch,
            season=season,
            ahead_behind="Ahead or Behind",
            clutch_time="Last 5 Minutes",
            point_diff=5,
            per_mode_detailed="PerGame",
            measure_type_detailed_defense="Base",
        )
        result = clutch.get_normalized_dict().get("LeagueDashPlayerClutch", [])

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
        return result

    def get_defensive_play_type_stats(
        self,
        play_type: str,
        season: str = "2024-25",
        season_type: str = "Regular Season",
    ) -> list[dict]:
        """Get defensive synergy play type stats for all players.

        Args:
            play_type: Play type name (e.g., "Isolation", "PRBallHandler")
            season: NBA season string (e.g., "2024-25")
            season_type: "Regular Season" or "Playoffs"

        Returns:
            List of player defensive play type stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = (
            f"{CacheKeyPrefix.NBA_DEFENSIVE_PLAY_TYPE_STATS.value}:{play_type}:{season}"
        )

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info(
                    "Cache hit for defensive play type stats (type: %s, season: %s)",
                    play_type,
                    season,
                )
                return cached

        logger.info(
            "Cache miss for defensive play type stats (type: %s, season: %s), "
            "fetching from API",
            play_type,
            season,
        )

        synergy = self._request_with_retry(
            SynergyPlayTypes,
            season=season,
            season_type_all_star=season_type,
            play_type_nullable=play_type,
            player_or_team_abbreviation="P",  # Player stats
            type_grouping_nullable="defensive",  # Defensive play types
        )
        result = synergy.get_normalized_dict().get("SynergyPlayType", [])

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
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
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for rim protection stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for rim protection stats (season: %s), fetching from API",
            season,
        )
        rim = self._request_with_retry(
            LeagueDashPtDefend,
            season=season,
            per_mode_simple="Totals",
            defense_category="Less Than 6Ft",
        )
        result = rim.get_normalized_dict()["LeagueDashPTDefend"]

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
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
            cached = redis_cache.get(cache_key)
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
            LeagueDashPtDefend,
            season=season,
            per_mode_simple="Totals",
            defense_category="3 Pointers",
        )
        result = three_pt.get_normalized_dict()["LeagueDashPTDefend"]

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
        return result

    def get_team_stats(
        self, season: str = "2024-25", measure_type: str = "Base"
    ) -> list[dict]:
        """Get team-level stats for all teams.

        Args:
            season: NBA season string (e.g., "2024-25")
            measure_type: Stat category - "Base" for traditional totals,
                          "Advanced" for pace/ratings

        Returns:
            List of team stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = f"{CacheKeyPrefix.NBA_TEAM_STATS.value}:{measure_type}:{season}"

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info(
                    "Cache hit for team stats (measure: %s, season: %s)",
                    measure_type,
                    season,
                )
                return cached

        logger.info(
            "Cache miss for team stats (measure: %s, season: %s), fetching from API",
            measure_type,
            season,
        )
        stats = self._request_with_retry(
            LeagueDashTeamStats,
            season=season,
            per_mode_detailed="Totals",
            measure_type_detailed_defense=measure_type,
        )
        result = stats.get_normalized_dict()["LeagueDashTeamStats"]

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
        return result

    def get_per100_stats(self, season: str = "2024-25") -> list[dict]:
        """Get per-100 possessions stats for all players.

        Args:
            season: NBA season string (e.g., "2024-25")

        Returns:
            List of player per-100 possession stat dictionaries

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_PER100_STATS, season)

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for per-100 stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for per-100 stats (season: %s), fetching from API", season
        )
        stats = self._request_with_retry(
            LeagueDashPlayerStats,
            season=season,
            per_mode_detailed="Per100Possessions",
            measure_type_detailed_defense="Base",
        )
        result = stats.get_normalized_dict()["LeagueDashPlayerStats"]

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
        return result

    def get_career_stats(self, player_id: int) -> dict:
        """Get career stats for a single player.

        Returns multiple datasets including SeasonTotalsRegularSeason
        and CareerTotalsRegularSeason.

        Args:
            player_id: NBA player ID

        Returns:
            Dictionary with dataset names as keys and list of row dicts as values

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        cache_key = f"{CacheKeyPrefix.NBA_CAREER_STATS.value}:{player_id}"

        # Check cache first (unless bypassed)
        if not self.bypass_cache:
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for career stats (player: %d)", player_id)
                return cached

        logger.info(
            "Cache miss for career stats (player: %d), fetching from API", player_id
        )
        career = self._request_with_retry(
            PlayerCareerStats,
            player_id=player_id,
            per_mode36="PerGame",
        )
        result = career.get_normalized_dict()

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
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
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for catch-shoot stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for catch-shoot stats (season: %s), fetching from API", season
        )
        stats = self._request_with_retry(
            LeagueDashPtStats,
            season=season,
            per_mode_simple="PerGame",
            player_or_team="Player",
            pt_measure_type="CatchShoot",
        )
        result = stats.get_normalized_dict()["LeagueDashPtStats"]

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
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
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for pull-up stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for pull-up stats (season: %s), fetching from API", season
        )
        stats = self._request_with_retry(
            LeagueDashPtStats,
            season=season,
            per_mode_simple="PerGame",
            player_or_team="Player",
            pt_measure_type="PullUpShot",
        )
        result = stats.get_normalized_dict()["LeagueDashPtStats"]

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
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
            cached = redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for drive stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for drive stats (season: %s), fetching from API", season
        )
        stats = self._request_with_retry(
            LeagueDashPtStats,
            season=season,
            per_mode_simple="PerGame",
            player_or_team="Player",
            pt_measure_type="Drives",
        )
        result = stats.get_normalized_dict()["LeagueDashPtStats"]

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
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
            cached = redis_cache.get(cache_key)
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
            LeagueDashPtStats,
            season=season,
            per_mode_simple="PerGame",
            player_or_team="Player",
            pt_measure_type="Efficiency",
        )
        result = efficiency.get_normalized_dict()["LeagueDashPtStats"]

        # Cache the result
        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
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
            cached = redis_cache.get(cache_key)
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

        matchups = self._request_with_retry(LeagueSeasonMatchups, **kwargs)
        result = matchups.get_normalized_dict()["SeasonMatchups"]

        redis_cache.set(cache_key, result, ttl=settings.cache_ttl_tracking_stats)
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

    def fetch_all_defensive_play_type_data(
        self,
        season: str = "2024-25",
        progress_callback: Optional[callable] = None,
    ) -> dict[int, PlayerDefensivePlayTypeData]:
        """Fetch and combine defensive play type data for all players.

        This method fetches defensive synergy play type stats for key defensive
        play types (Isolation, PRBallHandler, Postup, Spotup, Transition) and
        combines them into PlayerDefensivePlayTypeData objects.

        Args:
            season: NBA season string (e.g., "2024-25")
            progress_callback: Optional callback(play_type_idx, total, play_type_name)

        Returns:
            Dict keyed by player_id with aggregated PlayerDefensivePlayTypeData

        Raises:
            CircuitBreakerError: If circuit breaker is open
            RateLimitError: If rate limited after max retries
        """
        logger.info("Fetching defensive play type data for season %s...", season)
        print(f"Fetching defensive play type data for season {season}...")

        combined: dict[int, PlayerDefensivePlayTypeData] = {}
        play_types = list(DEFENSIVE_PLAY_TYPE_MAPPING.items())

        for idx, (field_name, api_name) in enumerate(play_types):
            if progress_callback:
                progress_callback(idx + 1, len(play_types), api_name)

            logger.info(
                "Fetching defensive %s stats (%d/%d)...",
                api_name,
                idx + 1,
                len(play_types),
            )
            print(
                f"  - Fetching defensive {api_name} stats "
                f"({idx + 1}/{len(play_types)})..."
            )

            try:
                play_type_data = self.get_defensive_play_type_stats(api_name, season)

                for player in play_type_data:
                    player_id = player.get("PLAYER_ID")
                    if not player_id:
                        continue

                    # Create or get existing player data
                    if player_id not in combined:
                        combined[player_id] = PlayerDefensivePlayTypeData(
                            player_id=player_id,
                            player_name=player.get("PLAYER_NAME", ""),
                            team_abbreviation=player.get("TEAM_ABBREVIATION", ""),
                        )

                    # Create metrics for this defensive play type
                    poss = player.get("POSS", 0) or 0
                    pts = player.get("PTS", 0) or 0
                    fgm = player.get("FGM", 0) or 0
                    fga = player.get("FGA", 0) or 0
                    ppp = Decimal(str(player.get("PPP", 0) or 0))
                    fg_pct = Decimal(str(player.get("FG_PCT", 0) or 0))
                    percentile = Decimal(str(player.get("PERCENTILE", 0) or 0))

                    metrics = DefensivePlayTypeMetrics(
                        possessions=poss,
                        points=pts,
                        fgm=fgm,
                        fga=fga,
                        ppp=ppp,
                        fg_pct=fg_pct,
                        percentile=percentile,
                    )

                    # Set the metrics on the player data
                    setattr(combined[player_id], field_name, metrics)

                    # Update total possessions
                    combined[player_id].total_poss += poss

            except Exception as e:
                logger.warning("Failed to fetch defensive %s stats: %s", api_name, e)
                print(
                    f"    Warning: Failed to fetch defensive {api_name} stats: {e}"
                )
                continue

        logger.info(
            "Combined defensive play type data for %d players", len(combined)
        )
        print(
            f"  - Combined defensive play type data for {len(combined)} players"
        )
        return combined


# Singleton instance
nba_data_service = NBADataService()
