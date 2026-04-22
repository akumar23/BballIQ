"""Synergy offensive/defensive play-type stat fetchers."""

from __future__ import annotations

import logging
from decimal import Decimal

from app.services import nba_data as _nd
from app.services.nba.constants import (
    DEFENSIVE_PLAY_TYPE_MAPPING,
    PLAY_TYPE_MAPPING,
)
from app.services.nba.models import (
    DefensivePlayTypeMetrics,
    PlayerDefensivePlayTypeData,
    PlayerPlayTypeData,
    PlayTypeMetrics,
)
from app.services.redis_cache import CacheKeyPrefix

logger = logging.getLogger(__name__)


class PlayTypesMixin:
    """Offensive and defensive Synergy play-type fetchers."""

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
            cached = _nd.redis_cache.get(cache_key)
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
            _nd.SynergyPlayTypes,
            season=season,
            season_type_all_star=season_type,
            play_type_nullable=play_type,
            player_or_team_abbreviation="P",  # Player stats
            type_grouping_nullable="offensive",  # Offensive play types
        )
        result = synergy.get_normalized_dict().get("SynergyPlayType", [])

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def fetch_all_play_type_data(
        self,
        season: str = "2024-25",
        progress_callback: callable | None = None,
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
            cached = _nd.redis_cache.get(cache_key)
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
            _nd.SynergyPlayTypes,
            season=season,
            season_type_all_star=season_type,
            play_type_nullable=play_type,
            player_or_team_abbreviation="P",  # Player stats
            type_grouping_nullable="defensive",  # Defensive play types
        )
        result = synergy.get_normalized_dict().get("SynergyPlayType", [])

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
        return result

    def fetch_all_defensive_play_type_data(
        self,
        season: str = "2024-25",
        progress_callback: callable | None = None,
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
