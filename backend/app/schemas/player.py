from decimal import Decimal

from pydantic import BaseModel, ConfigDict


class PlayerBase(BaseModel):
    nba_id: int
    name: str
    position: str | None
    team_abbreviation: str | None


class PlayerMetrics(BaseModel):
    offensive_metric: Decimal | None
    defensive_metric: Decimal | None
    overall_metric: Decimal | None
    offensive_percentile: int | None
    defensive_percentile: int | None
    # Present only on the composite /overall leaderboard — weighted z-score
    # aggregate across scoring/playmaking/rebounding/defense/impact.
    composite_score: float | None = None
    composite_rank: int | None = None
    category_scores: dict[str, float] | None = None


class PlayerList(PlayerBase):
    id: int
    metrics: PlayerMetrics | None

    model_config = ConfigDict(from_attributes=True)


class PlayerTrackingStats(BaseModel):
    touches: int | None
    points_per_touch: float | None
    time_of_possession: float | None
    deflections: int | None
    contested_shots: int | None


class PlayerPerGameStats(BaseModel):
    id: int
    nba_id: int
    name: str
    position: str | None
    team_abbreviation: str | None
    games_played: int | None
    ppg: Decimal | None
    rpg: Decimal | None
    apg: Decimal | None
    mpg: Decimal | None
    spg: Decimal | None
    bpg: Decimal | None

    model_config = ConfigDict(from_attributes=True)


class PlayerDetail(PlayerList):
    season: str
    games_played: int | None
    tracking_stats: PlayerTrackingStats | None

    model_config = ConfigDict(from_attributes=True)


class PlayerCardOption(BaseModel):
    """A single player+season entry for the player card selector dropdown."""

    id: int
    name: str
    position: str | None
    team_abbreviation: str | None
    season: str

    model_config = ConfigDict(from_attributes=True)


class PlayerCardOptionPage(BaseModel):
    """Paginated envelope for ``/players/available``.

    Only returned when the caller opts in by passing ``limit`` or ``offset``.
    The bare-array legacy shape is kept for callers that pass neither.

    TODO(api-v2): drop the legacy bare-array shape once the frontend is
    migrated to always pass pagination params. Tracked in follow-up ticket.
    """

    items: list[PlayerCardOption]
    total: int
    limit: int
    offset: int


class PlayerSearchResult(BaseModel):
    """A single fuzzy-search hit on players.name."""

    id: int
    nba_id: int
    name: str
    position: str | None
    team_abbreviation: str | None
    # Only populated when the pg_trgm backend is active; None on the
    # ilike fallback path.
    similarity: float | None = None

    model_config = ConfigDict(from_attributes=True)
