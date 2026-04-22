"""Dataclasses for aggregated NBA API data.

These types are the public data contract returned by the various fetch_* and
get_* methods on :class:`NBADataService`. They are intentionally plain
dataclasses rather than pydantic models — the shim at :mod:`app.services.nba_data`
re-exports them verbatim so existing callers keep working.
"""

from __future__ import annotations

from dataclasses import dataclass
from decimal import Decimal


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
    handoff: PlayTypeMetrics | None = None

    # Total possessions across all play types
    total_poss: int = 0


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
    paint_touches: int
    post_touches: int
    elbow_touches: int
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
    off_loose_balls_recovered: int
    def_loose_balls_recovered: int
    pct_loose_balls_off: Decimal
    pct_loose_balls_def: Decimal
    box_outs: int
    box_outs_off: int
    box_outs_def: int
    box_out_player_team_rebs: int
    box_out_player_rebs: int
    pct_box_outs_off: Decimal
    pct_box_outs_def: Decimal
    pct_box_outs_team_reb: Decimal
    pct_box_outs_reb: Decimal
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
    minutes: Decimal
    games_played: int
    rebounds: int
    plus_minus: int
