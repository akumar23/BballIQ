"""Backwards-compatible facade for the split NBA data package.

The implementation lives in :mod:`app.services.nba`. This module is the stable
public surface — all existing ``from app.services.nba_data import X`` callsites
(tests, tasks, scripts, other services) keep resolving against these re-exports.

The module-level symbols below (``settings``, ``redis_cache``, the endpoint
classes, etc.) intentionally stay defined at this module's top level so that
existing ``unittest.mock.patch("app.services.nba_data.<name>", ...)`` sites
still take effect — the mixins resolve these names by attribute access on this
module (``_nd.<name>``), which honours the monkeypatch at call time.
"""

from __future__ import annotations

import logging

# Re-exported API endpoint classes. Mixins look these up via
# ``_nd.<Endpoint>`` so test patches of ``app.services.nba_data.<Endpoint>``
# continue to take effect after the split.
from nba_api.stats.endpoints import (
    CommonAllPlayers,
    LeagueDashPlayerStats,
)
from nba_api.stats.endpoints.leaguedashlineups import LeagueDashLineups
from nba_api.stats.endpoints.leaguedashplayerbiostats import (
    LeagueDashPlayerBioStats,
)
from nba_api.stats.endpoints.leaguedashplayerclutch import LeagueDashPlayerClutch
from nba_api.stats.endpoints.leaguedashplayerptshot import LeagueDashPlayerPtShot
from nba_api.stats.endpoints.leaguedashplayershotlocations import (
    LeagueDashPlayerShotLocations,
)
from nba_api.stats.endpoints.leaguedashptdefend import LeagueDashPtDefend
from nba_api.stats.endpoints.leaguedashptstats import LeagueDashPtStats
from nba_api.stats.endpoints.leaguedashteamstats import LeagueDashTeamStats
from nba_api.stats.endpoints.leaguehustlestatsplayer import LeagueHustleStatsPlayer
from nba_api.stats.endpoints.leagueseasonmatchups import LeagueSeasonMatchups
from nba_api.stats.endpoints.playercareerstats import PlayerCareerStats
from nba_api.stats.endpoints.playergamelogs import PlayerGameLogs
from nba_api.stats.endpoints.shotchartleaguewide import ShotChartLeagueWide
from nba_api.stats.endpoints.synergyplaytypes import SynergyPlayTypes
from nba_api.stats.endpoints.teamplayeronoffsummary import TeamPlayerOnOffSummary
from nba_api.stats.static import teams as nba_teams

from app.core.config import settings

# Constants and dataclass models — re-exported verbatim for existing callers.
from app.services.nba.constants import (
    DEFENSIVE_PLAY_TYPE_MAPPING,
    PLAY_TYPE_MAPPING,
)
from app.services.nba.models import (
    DefensivePlayTypeMetrics,
    LineupData,
    PlayerDefensivePlayTypeData,
    PlayerOnOffData,
    PlayerPlayTypeData,
    PlayerTrackingData,
    PlayTypeMetrics,
)
from app.services.rate_limiter import (
    CircuitBreakerError,
    RateLimitError,
    calculate_backoff_delay,
    get_nba_session,
    nba_api_circuit_breaker,
)
from app.services.redis_cache import (
    CacheKeyPrefix,
    redis_cache,
)

logger = logging.getLogger(__name__)

# Mixin imports must come AFTER the patchable symbols above so that during
# the mixins' top-level import they can safely bind ``from app.services import
# nba_data as _nd``; attribute access on ``_nd`` happens lazily inside method
# bodies, by which time this module is fully populated.
from app.services.nba.advanced import AdvancedMixin  # noqa: E402
from app.services.nba.base import BaseNBAClient  # noqa: E402
from app.services.nba.defense import DefenseMixin  # noqa: E402
from app.services.nba.lineups import LineupsMixin  # noqa: E402
from app.services.nba.play_types import PlayTypesMixin  # noqa: E402
from app.services.nba.players import PlayersMixin  # noqa: E402
from app.services.nba.shots import ShotsMixin  # noqa: E402
from app.services.nba.tracking import TrackingMixin  # noqa: E402
from app.services.nba.traditional import TraditionalMixin  # noqa: E402


class NBADataService(
    PlayersMixin,
    TraditionalMixin,
    TrackingMixin,
    DefenseMixin,
    ShotsMixin,
    AdvancedMixin,
    PlayTypesMixin,
    LineupsMixin,
    BaseNBAClient,
):
    """Fetches tracking and traditional stats from NBA API.

    This service implements robust rate limiting with:
    - Exponential backoff with jitter for retries
    - Circuit breaker to prevent hammering a failing API
    - Configurable retry logic
    - Proper HTTP headers for NBA API authentication
    - Redis caching to minimize external API calls

    The class is composed of per-family mixins (see :mod:`app.services.nba`).
    ``BaseNBAClient`` is listed last so that the mixins — which do not override
    any of its methods — resolve ahead of it in MRO, matching the single-class
    ordering that existed before the split.
    """


# Singleton instance
nba_data_service = NBADataService()


__all__ = [
    "CacheKeyPrefix",
    "CircuitBreakerError",
    "CommonAllPlayers",
    "DEFENSIVE_PLAY_TYPE_MAPPING",
    "DefensivePlayTypeMetrics",
    "LeagueDashLineups",
    "LeagueDashPlayerBioStats",
    "LeagueDashPlayerClutch",
    "LeagueDashPlayerPtShot",
    "LeagueDashPlayerShotLocations",
    "LeagueDashPlayerStats",
    "LeagueDashPtDefend",
    "LeagueDashPtStats",
    "LeagueDashTeamStats",
    "LeagueHustleStatsPlayer",
    "LeagueSeasonMatchups",
    "LineupData",
    "NBADataService",
    "PLAY_TYPE_MAPPING",
    "PlayTypeMetrics",
    "PlayerCareerStats",
    "PlayerDefensivePlayTypeData",
    "PlayerGameLogs",
    "PlayerOnOffData",
    "PlayerPlayTypeData",
    "PlayerTrackingData",
    "RateLimitError",
    "ShotChartLeagueWide",
    "SynergyPlayTypes",
    "TeamPlayerOnOffSummary",
    "calculate_backoff_delay",
    "get_nba_session",
    "logger",
    "nba_api_circuit_breaker",
    "nba_data_service",
    "nba_teams",
    "redis_cache",
    "settings",
]
