"""Pydantic schemas for play type statistics."""

from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PlayTypeMetrics(BaseModel):
    """Metrics for a single play type."""

    possessions: int | None
    points: int | None
    ppp: Decimal | None  # Points per possession
    fg_pct: Decimal | None  # Field goal percentage
    frequency: Decimal | None  # Frequency of this play type
    ppp_percentile: int | None = None


class SpotUpMetrics(PlayTypeMetrics):
    """Metrics for spot-up plays (includes 3-point tracking)."""

    fg3m: int | None = None
    fg3a: int | None = None
    fg3_pct: Decimal | None = None


class PlayerPlayTypeStats(BaseModel):
    """Full play type stats for a player."""

    id: int
    nba_id: int
    name: str
    position: str | None
    team_abbreviation: str | None
    season: str
    total_poss: int | None

    isolation: PlayTypeMetrics | None = None
    pnr_ball_handler: PlayTypeMetrics | None = None
    pnr_roll_man: PlayTypeMetrics | None = None
    post_up: PlayTypeMetrics | None = None
    spot_up: SpotUpMetrics | None = None
    transition: PlayTypeMetrics | None = None
    cut: PlayTypeMetrics | None = None
    off_screen: PlayTypeMetrics | None = None

    model_config = ConfigDict(from_attributes=True)


class PlayTypeLeaderboardEntry(BaseModel):
    """Entry in the play type leaderboard."""

    rank: int | None = None
    id: int
    nba_id: int
    name: str
    position: str | None
    team_abbreviation: str | None
    possessions: int | None
    points: int | None
    ppp: Decimal | None
    fg_pct: Decimal | None
    frequency: Decimal | None
    ppp_percentile: int | None = None

    model_config = ConfigDict(from_attributes=True)


class PlayTypeLeaderboardResponse(BaseModel):
    """Response for play type leaderboard endpoint."""

    play_type: str
    sort_by: str
    entries: list[PlayTypeLeaderboardEntry]
