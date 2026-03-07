from decimal import Decimal

from pydantic import BaseModel


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


class PlayerList(PlayerBase):
    id: int
    metrics: PlayerMetrics | None

    class Config:
        from_attributes = True


class PlayerTrackingStats(BaseModel):
    touches: int | None
    points_per_touch: Decimal | None
    time_of_possession: Decimal | None
    deflections: int | None
    contested_shots: int | None


class PlayerDetail(PlayerList):
    season: str
    games_played: int | None
    tracking_stats: PlayerTrackingStats | None

    class Config:
        from_attributes = True
