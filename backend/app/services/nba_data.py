"""Service for fetching data from NBA API and PBP Stats."""

import time
from dataclasses import dataclass
from decimal import Decimal

from nba_api.stats.endpoints import (
    CommonAllPlayers,
    LeagueDashPlayerStats,
)
from nba_api.stats.endpoints.leaguehustlestatsplayer import LeagueHustleStatsPlayer
from nba_api.stats.endpoints.leaguedashptstats import LeagueDashPtStats
from nba_api.stats.endpoints.leaguedashptdefend import LeagueDashPtDefend

from app.core.config import settings


# Request delay to avoid rate limiting
REQUEST_DELAY = 0.6


@dataclass
class PlayerTrackingData:
    """Aggregated tracking data for a player."""
    player_id: int
    player_name: str
    team_abbreviation: str

    # Offensive tracking
    touches: int
    front_court_touches: int
    time_of_possession: Decimal
    avg_seconds_per_touch: Decimal
    avg_dribbles_per_touch: Decimal
    points_per_touch: Decimal

    # Defensive tracking
    deflections: int
    contested_shots_2pt: int
    contested_shots_3pt: int
    charges_drawn: int
    loose_balls_recovered: int

    # Traditional stats for calculations
    points: int
    assists: int
    turnovers: int
    fta: int
    minutes: Decimal


class NBADataService:
    """Fetches tracking and traditional stats from NBA API."""

    def __init__(self):
        self.cache_dir = settings.nba_api_cache_dir

    def _request_with_delay(self, endpoint_class, **kwargs):
        """Make API request with delay to avoid rate limiting."""
        time.sleep(REQUEST_DELAY)
        return endpoint_class(**kwargs)

    def get_all_players(self, season: str = "2024-25") -> list[dict]:
        """Get all active players for a season."""
        players = self._request_with_delay(
            CommonAllPlayers,
            is_only_current_season=1,
            season=season,
        )
        return players.get_normalized_dict()["CommonAllPlayers"]

    def get_traditional_stats(self, season: str = "2024-25") -> list[dict]:
        """Get traditional box score stats for all players."""
        stats = self._request_with_delay(
            LeagueDashPlayerStats,
            season=season,
            per_mode_detailed="Totals",
            measure_type_detailed_defense="Base",
        )
        return stats.get_normalized_dict()["LeagueDashPlayerStats"]

    def get_touch_stats(self, season: str = "2024-25") -> list[dict]:
        """
        Get touch tracking stats for all players.

        Returns: touches, front_court_touches, time_of_possession,
                 avg_sec_per_touch, avg_drib_per_touch, pts_per_touch
        """
        touches = self._request_with_delay(
            LeagueDashPtStats,
            season=season,
            per_mode_simple="Totals",
            player_or_team="Player",
            pt_measure_type="Possessions",
        )
        return touches.get_normalized_dict()["LeagueDashPtStats"]

    def get_hustle_stats(self, season: str = "2024-25") -> list[dict]:
        """
        Get hustle stats for all players.

        Returns: deflections, contested_shots, charges_drawn,
                 loose_balls_recovered, box_outs
        """
        hustle = self._request_with_delay(
            LeagueHustleStatsPlayer,
            season=season,
            per_mode_time="Totals",
        )
        return hustle.get_normalized_dict()["HustleStatsPlayer"]

    def get_defensive_stats(self, season: str = "2024-25") -> list[dict]:
        """
        Get defensive tracking stats for all players.

        Returns: dfg%, contested_2pt, contested_3pt
        """
        defense = self._request_with_delay(
            LeagueDashPtDefend,
            season=season,
            per_mode_simple="Totals",
            defense_category="Overall",
        )
        return defense.get_normalized_dict()["LeagueDashPtDefend"]

    def fetch_all_tracking_data(self, season: str = "2024-25") -> dict[int, PlayerTrackingData]:
        """
        Fetch and combine all tracking data for all players.

        Returns dict keyed by player_id with aggregated PlayerTrackingData.
        """
        print(f"Fetching tracking data for season {season}...")

        # Fetch all data sources
        print("  - Fetching traditional stats...")
        traditional = {p["PLAYER_ID"]: p for p in self.get_traditional_stats(season)}

        print("  - Fetching touch stats...")
        touches = {p["PLAYER_ID"]: p for p in self.get_touch_stats(season)}

        print("  - Fetching hustle stats...")
        hustle = {p["PLAYER_ID"]: p for p in self.get_hustle_stats(season)}

        print("  - Fetching defensive stats...")
        defense = {p["PLAYER_ID"]: p for p in self.get_defensive_stats(season)}

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

                # Offensive tracking
                touches=touch.get("TOUCHES", 0) or 0,
                front_court_touches=touch.get("FRONT_CT_TOUCHES", 0) or 0,
                time_of_possession=Decimal(str(touch.get("TIME_OF_POSS", 0) or 0)),
                avg_seconds_per_touch=Decimal(str(touch.get("AVG_SEC_PER_TOUCH", 0) or 0)),
                avg_dribbles_per_touch=Decimal(str(touch.get("AVG_DRIB_PER_TOUCH", 0) or 0)),
                points_per_touch=Decimal(str(touch.get("PTS_PER_TOUCH", 0) or 0)),

                # Defensive tracking (from hustle stats)
                deflections=hust.get("DEFLECTIONS", 0) or 0,
                contested_shots_2pt=hust.get("CONTESTED_SHOTS_2PT", 0) or 0,
                contested_shots_3pt=hust.get("CONTESTED_SHOTS_3PT", 0) or 0,
                charges_drawn=hust.get("CHARGES_DRAWN", 0) or 0,
                loose_balls_recovered=hust.get("LOOSE_BALLS_RECOVERED", 0) or 0,

                # Traditional stats
                points=trad.get("PTS", 0) or 0,
                assists=trad.get("AST", 0) or 0,
                turnovers=trad.get("TOV", 0) or 0,
                fta=trad.get("FTA", 0) or 0,
                minutes=Decimal(str(trad.get("MIN", 0) or 0)),
            )

        print(f"  - Combined data for {len(combined)} players")
        return combined


# Singleton instance
nba_data_service = NBADataService()
