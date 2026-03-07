"""Service for fetching data from PBP Stats."""

from dataclasses import dataclass
from decimal import Decimal

from pbpstats.client import Client
from pbpstats.resources.enhanced_pbp import EnhancedPbpItem

from app.core.config import settings


@dataclass
class PossessionStats:
    """Possession-level stats for a player."""
    player_id: int
    player_name: str

    # Offensive possessions
    total_possessions: int
    points_per_possession: Decimal
    turnover_rate: Decimal
    assist_rate: Decimal

    # Play type breakdown (possessions)
    isolation_poss: int
    pnr_ball_handler_poss: int
    pnr_roll_man_poss: int
    post_up_poss: int
    spot_up_poss: int
    transition_poss: int
    cut_poss: int


class PBPStatsService:
    """Fetches play-by-play derived stats from pbpstats."""

    def __init__(self):
        self.settings = {
            "dir": settings.nba_api_cache_dir,
            "Boxscore": {"source": "file", "data_provider": "stats_nba"},
            "Possessions": {"source": "file", "data_provider": "stats_nba"},
        }

    def get_client(self) -> Client:
        """Get configured pbpstats client."""
        return Client(self.settings)

    def get_season_totals(
        self,
        season: str = "2024-25",
        season_type: str = "Regular Season",
    ) -> dict:
        """
        Get season totals for all players.

        Note: This requires having cached game data locally.
        For initial setup, you need to fetch games first.
        """
        client = Client({
            "Games": {"source": "web", "data_provider": "data_nba"},
        })

        try:
            season_obj = client.Season("nba", season, season_type)
            return {
                "games": [g for g in season_obj.games.items],
            }
        except Exception as e:
            print(f"Error fetching season data: {e}")
            return {"games": []}

    def get_game_possessions(self, game_id: str) -> list:
        """Get all possessions for a specific game."""
        client = self.get_client()

        try:
            game = client.Game(game_id)
            return list(game.possessions.items)
        except Exception as e:
            print(f"Error fetching game {game_id}: {e}")
            return []


# Singleton instance
pbp_stats_service = PBPStatsService()
