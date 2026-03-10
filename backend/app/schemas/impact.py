from decimal import Decimal

from pydantic import BaseModel


class OnOffStats(BaseModel):
    """On/Off court statistics."""

    on_court_minutes: Decimal | None
    on_court_net_rating: Decimal | None
    on_court_off_rating: Decimal | None
    on_court_def_rating: Decimal | None
    off_court_minutes: Decimal | None
    off_court_net_rating: Decimal | None
    off_court_off_rating: Decimal | None
    off_court_def_rating: Decimal | None
    net_rating_diff: Decimal | None
    off_rating_diff: Decimal | None
    def_rating_diff: Decimal | None


class ImpactContext(BaseModel):
    """Contextual factors used in impact calculation."""

    avg_teammate_net_rating: Decimal | None
    teammate_adjustment: Decimal | None
    pct_minutes_vs_starters: Decimal | None
    opponent_quality_factor: Decimal | None
    reliability_factor: Decimal | None


class ImpactRating(BaseModel):
    """Contextualized impact ratings."""

    raw_net_rating_diff: Decimal | None
    raw_off_rating_diff: Decimal | None
    raw_def_rating_diff: Decimal | None
    contextualized_net_impact: Decimal | None
    contextualized_off_impact: Decimal | None
    contextualized_def_impact: Decimal | None
    impact_percentile: int | None
    offensive_impact_percentile: int | None
    defensive_impact_percentile: int | None


class PlayerImpact(BaseModel):
    """Full player impact data for the Impact page."""

    id: int
    nba_id: int
    name: str
    position: str | None
    team_abbreviation: str | None
    season: str
    on_off_stats: OnOffStats | None
    context: ImpactContext | None
    impact: ImpactRating | None

    class Config:
        from_attributes = True


class ImpactLeaderboardEntry(BaseModel):
    """Entry in the impact leaderboard."""

    id: int
    nba_id: int
    name: str
    position: str | None
    team_abbreviation: str | None
    contextualized_net_impact: Decimal | None
    contextualized_off_impact: Decimal | None
    contextualized_def_impact: Decimal | None
    raw_net_rating_diff: Decimal | None
    teammate_adjustment: Decimal | None
    reliability_factor: Decimal | None
    impact_percentile: int | None

    class Config:
        from_attributes = True
