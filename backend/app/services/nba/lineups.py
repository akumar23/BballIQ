"""5-man lineup and team player on/off stat fetchers."""

from __future__ import annotations

import logging
from decimal import Decimal

from nba_api.stats.static import teams as nba_teams

from app.services import nba_data as _nd
from app.services.nba.models import (
    LineupData,
    PlayerOnOffData,
    PlayerOnOffShootingData,
)
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

    def get_on_off_shooting_for_team(
        self, team_id: int, season: str = "2024-25"
    ) -> tuple[list[dict], list[dict]]:
        """Get team-shooting on/off splits for a single team.

        Mirrors :meth:`get_on_off_stats_for_team` but requests the
        ``Shooting`` measure type, which returns team eFG% and shot-class
        frequency splits (open 3PA, wide-open 3PA, catch-and-shoot share,
        pull-up share) for each player's on / off court splits.

        Args:
            team_id: NBA team ID.
            season: NBA season string.

        Returns:
            Tuple of (on_court_rows, off_court_rows). Each row is a raw
            NBA stats dict; field parsing happens in
            :meth:`get_all_on_off_shooting`.
        """
        data = self._request_with_retry(
            _nd.TeamPlayerOnOffSummary,
            team_id=team_id,
            season=season,
            per_mode_detailed="PerGame",
            measure_type_detailed_defense="Shooting",
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

    def get_all_on_off_shooting(
        self,
        season: str = "2024-25",
        progress_callback: callable | None = None,
    ) -> dict[int, PlayerOnOffShootingData]:
        """Get team-shooting on/off splits for every player across all teams.

        Iterates the 30 teams calling :meth:`get_on_off_shooting_for_team`
        for each, then joins the on/off splits per player. Cached as a
        plain JSON dict keyed by ``str(player_id)``.

        Args:
            season: NBA season string.
            progress_callback: Optional callback(team_idx, total, team_name).

        Returns:
            Dict keyed by player_id with :class:`PlayerOnOffShootingData`.
        """
        cache_key = self._get_cache_key(CacheKeyPrefix.NBA_ON_OFF_SHOOTING, season)

        if not self.bypass_cache:
            cached = _nd.redis_cache.get(cache_key)
            if cached is not None:
                logger.info(
                    "Cache hit for on/off shooting (season: %s)", season
                )
                return {
                    int(k): _on_off_shooting_from_cache(v)
                    for k, v in cached.items()
                }

        logger.info(
            "Cache miss for on/off shooting (season: %s), fetching from API", season
        )

        all_teams = nba_teams.get_teams()
        combined: dict[int, PlayerOnOffShootingData] = {}

        for idx, team in enumerate(all_teams):
            team_id = team["id"]
            team_abbr = team["abbreviation"]
            team_name = team["full_name"]

            if progress_callback:
                progress_callback(idx + 1, len(all_teams), team_name)

            logger.info(
                "Fetching on/off shooting for %s (%d/%d)",
                team_abbr,
                idx + 1,
                len(all_teams),
            )

            try:
                on_court, off_court = self.get_on_off_shooting_for_team(
                    team_id, season
                )
                off_by_pid = {p["VS_PLAYER_ID"]: p for p in off_court}

                for player in on_court:
                    pid = player["VS_PLAYER_ID"]
                    off_row = off_by_pid.get(pid, {})
                    combined[pid] = _parse_on_off_shooting_row(
                        player, off_row, team_id, team_abbr
                    )

            except Exception as e:
                logger.warning(
                    "Failed to fetch on/off shooting for %s: %s", team_abbr, e
                )
                continue

        logger.info(
            "Collected on/off shooting data for %d players", len(combined)
        )

        cache_data = {
            str(k): _on_off_shooting_to_cache(v) for k, v in combined.items()
        }
        _nd.redis_cache.set(
            cache_key, cache_data, ttl=_nd.settings.cache_ttl_tracking_stats
        )

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


# ---------------------------------------------------------------------------
# Shooting on/off parsing helpers
# ---------------------------------------------------------------------------
#
# Centralised here (rather than inlined in the mixin) so the assumed NBA
# Stats response shape lives in one obvious place. The ``Shooting`` measure
# of ``TeamPlayerOnOffSummary`` is documented to return a row per player
# with the following columns relevant to gravity (verified against the
# sibling ``Base`` measure pattern at ``get_on_off_stats_for_team`` —
# the API uses identical key conventions across measure types):
#
#   EFG_PCT                    -- team effective FG% with player on/off
#   PCT_OPEN_3PA               -- share of 3PA that were "open" (4-6 ft)
#   PCT_WIDE_OPEN_3PA          -- share of 3PA that were wide open (6+ ft)
#   PCT_FGA_CATCH_SHOOT        -- catch-and-shoot share of total FGA
#   PCT_FGA_PULL_UP            -- pull-up share of total FGA
#   MIN                        -- on/off minutes (sample-size signal)
#
# If the live NBA API uses slightly different column names, only the
# small mapping below needs to change.

_SHOOTING_ON_OFF_FIELDS = {
    "efg": "EFG_PCT",
    "open3_freq": "PCT_OPEN_3PA",
    "wide_open3_freq": "PCT_WIDE_OPEN_3PA",
    "catch_shoot_share": "PCT_FGA_CATCH_SHOOT",
    "pullup_share": "PCT_FGA_PULL_UP",
    "minutes": "MIN",
}


def _shooting_field(row: dict, key: str) -> Decimal:
    """Coerce a single shooting on/off field to ``Decimal``.

    Treats missing / non-numeric values as zero, matching the convention
    used by :meth:`LineupsMixin.get_all_on_off_stats` for base on/off.
    """
    column = _SHOOTING_ON_OFF_FIELDS[key]
    raw = row.get(column, 0) or 0
    try:
        return Decimal(str(raw))
    except (ArithmeticError, ValueError):
        return Decimal("0")


def _parse_on_off_shooting_row(
    on_row: dict,
    off_row: dict,
    team_id: int,
    team_abbr: str,
) -> PlayerOnOffShootingData:
    """Build a :class:`PlayerOnOffShootingData` from on/off rows.

    Differentials are computed as ``on - off``. ``team_*_diff`` fields
    feed the gravity index's teammate-lift component directly.
    """
    on_min = _shooting_field(on_row, "minutes")
    off_min = _shooting_field(off_row, "minutes")

    on_efg = _shooting_field(on_row, "efg")
    off_efg = _shooting_field(off_row, "efg")
    on_open3 = _shooting_field(on_row, "open3_freq")
    off_open3 = _shooting_field(off_row, "open3_freq")
    on_wide_open3 = _shooting_field(on_row, "wide_open3_freq")
    off_wide_open3 = _shooting_field(off_row, "wide_open3_freq")
    on_cs = _shooting_field(on_row, "catch_shoot_share")
    off_cs = _shooting_field(off_row, "catch_shoot_share")
    on_pu = _shooting_field(on_row, "pullup_share")
    off_pu = _shooting_field(off_row, "pullup_share")

    return PlayerOnOffShootingData(
        player_id=on_row.get("VS_PLAYER_ID", 0),
        player_name=on_row.get("VS_PLAYER_NAME", "") or "",
        team_id=team_id,
        team_abbreviation=team_abbr,
        on_court_min=on_min,
        off_court_min=off_min,
        on_court_team_efg=on_efg,
        off_court_team_efg=off_efg,
        team_efg_diff=on_efg - off_efg,
        on_court_team_open3_freq=on_open3,
        off_court_team_open3_freq=off_open3,
        team_open3_freq_diff=on_open3 - off_open3,
        on_court_team_wide_open3_freq=on_wide_open3,
        off_court_team_wide_open3_freq=off_wide_open3,
        team_wide_open3_freq_diff=on_wide_open3 - off_wide_open3,
        on_court_team_catch_shoot_share=on_cs,
        off_court_team_catch_shoot_share=off_cs,
        team_catch_shoot_share_diff=on_cs - off_cs,
        on_court_team_pullup_share=on_pu,
        off_court_team_pullup_share=off_pu,
        team_pullup_share_diff=on_pu - off_pu,
    )


def _on_off_shooting_to_cache(d: PlayerOnOffShootingData) -> dict[str, str | int]:
    """Serialise a :class:`PlayerOnOffShootingData` as a JSON-safe dict."""
    return {
        "player_id": d.player_id,
        "player_name": d.player_name,
        "team_id": d.team_id,
        "team_abbreviation": d.team_abbreviation,
        "on_court_min": str(d.on_court_min),
        "off_court_min": str(d.off_court_min),
        "on_court_team_efg": str(d.on_court_team_efg),
        "off_court_team_efg": str(d.off_court_team_efg),
        "team_efg_diff": str(d.team_efg_diff),
        "on_court_team_open3_freq": str(d.on_court_team_open3_freq),
        "off_court_team_open3_freq": str(d.off_court_team_open3_freq),
        "team_open3_freq_diff": str(d.team_open3_freq_diff),
        "on_court_team_wide_open3_freq": str(d.on_court_team_wide_open3_freq),
        "off_court_team_wide_open3_freq": str(d.off_court_team_wide_open3_freq),
        "team_wide_open3_freq_diff": str(d.team_wide_open3_freq_diff),
        "on_court_team_catch_shoot_share": str(d.on_court_team_catch_shoot_share),
        "off_court_team_catch_shoot_share": str(
            d.off_court_team_catch_shoot_share
        ),
        "team_catch_shoot_share_diff": str(d.team_catch_shoot_share_diff),
        "on_court_team_pullup_share": str(d.on_court_team_pullup_share),
        "off_court_team_pullup_share": str(d.off_court_team_pullup_share),
        "team_pullup_share_diff": str(d.team_pullup_share_diff),
    }


def _on_off_shooting_from_cache(v: dict) -> PlayerOnOffShootingData:
    """Inverse of :func:`_on_off_shooting_to_cache`."""
    return PlayerOnOffShootingData(
        player_id=int(v["player_id"]),
        player_name=v["player_name"],
        team_id=int(v["team_id"]),
        team_abbreviation=v["team_abbreviation"],
        on_court_min=Decimal(str(v["on_court_min"])),
        off_court_min=Decimal(str(v["off_court_min"])),
        on_court_team_efg=Decimal(str(v["on_court_team_efg"])),
        off_court_team_efg=Decimal(str(v["off_court_team_efg"])),
        team_efg_diff=Decimal(str(v["team_efg_diff"])),
        on_court_team_open3_freq=Decimal(str(v["on_court_team_open3_freq"])),
        off_court_team_open3_freq=Decimal(str(v["off_court_team_open3_freq"])),
        team_open3_freq_diff=Decimal(str(v["team_open3_freq_diff"])),
        on_court_team_wide_open3_freq=Decimal(
            str(v["on_court_team_wide_open3_freq"])
        ),
        off_court_team_wide_open3_freq=Decimal(
            str(v["off_court_team_wide_open3_freq"])
        ),
        team_wide_open3_freq_diff=Decimal(str(v["team_wide_open3_freq_diff"])),
        on_court_team_catch_shoot_share=Decimal(
            str(v["on_court_team_catch_shoot_share"])
        ),
        off_court_team_catch_shoot_share=Decimal(
            str(v["off_court_team_catch_shoot_share"])
        ),
        team_catch_shoot_share_diff=Decimal(
            str(v["team_catch_shoot_share_diff"])
        ),
        on_court_team_pullup_share=Decimal(str(v["on_court_team_pullup_share"])),
        off_court_team_pullup_share=Decimal(
            str(v["off_court_team_pullup_share"])
        ),
        team_pullup_share_diff=Decimal(str(v["team_pullup_share_diff"])),
    )
