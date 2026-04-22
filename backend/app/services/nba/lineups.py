"""5-man lineup and team player on/off stat fetchers."""

from __future__ import annotations

import logging
from decimal import Decimal

from nba_api.stats.static import teams as nba_teams

from app.services import nba_data as _nd
from app.services.nba.models import LineupData, PlayerOnOffData
from app.services.redis_cache import CacheKeyPrefix

logger = logging.getLogger(__name__)


class LineupsMixin:
    """Lineup and on/off-court fetchers."""

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
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info("Cache hit for lineup stats (season: %s)", season)
                return cached

        logger.info(
            "Cache miss for lineup stats (season: %s), fetching from API", season
        )
        lineups = self._request_with_retry(
            _nd.LeagueDashLineups,
            season=season,
            per_mode_detailed="Totals",
            measure_type_detailed_defense="Base",
            group_quantity=5,  # 5-man lineups
        )
        result = lineups.get_normalized_dict()["Lineups"]

        # Cache the result
        _nd.redis_cache.set(cache_key, result, ttl=_nd.settings.cache_ttl_tracking_stats)
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
            _nd.TeamPlayerOnOffSummary,
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
        progress_callback: callable | None = None,
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
            cached = _nd.redis_cache.get(cache_key)
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
        _nd.redis_cache.set(cache_key, cache_data, ttl=_nd.settings.cache_ttl_tracking_stats)

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

            # Totals mode doesn't return OFF_RATING/DEF_RATING/NET_RATING,
            # so compute them from the box-score totals.
            fga = float(lineup.get("FGA", 0) or 0)
            oreb = float(lineup.get("OREB", 0) or 0)
            tov = float(lineup.get("TOV", 0) or 0)
            fta = float(lineup.get("FTA", 0) or 0)
            pts = float(lineup.get("PTS", 0) or 0)
            plus_minus = float(lineup.get("PLUS_MINUS", 0) or 0)

            # Standard possession estimate: FGA - OREB + TOV + 0.44 * FTA
            poss = fga - oreb + tov + 0.44 * fta

            if poss > 0:
                off_rating = Decimal(str(round(pts / poss * 100, 2)))
                net_rating = Decimal(str(round(plus_minus / poss * 100, 2)))
                def_rating = off_rating - net_rating
            else:
                off_rating = Decimal("0")
                def_rating = Decimal("0")
                net_rating = Decimal("0")

            lineups.append(
                LineupData(
                    lineup_id="-".join(str(p) for p in sorted(player_ids)),
                    player_ids=player_ids,
                    player_names=player_names,
                    team_id=lineup.get("TEAM_ID", 0),
                    team_abbreviation=lineup.get("TEAM_ABBREVIATION", ""),
                    games_played=lineup.get("GP", 0) or 0,
                    minutes=Decimal(str(lineup.get("MIN", 0) or 0)),
                    plus_minus=Decimal(str(plus_minus)),
                    off_rating=off_rating,
                    def_rating=def_rating,
                    net_rating=net_rating,
                )
            )

        return lineups
