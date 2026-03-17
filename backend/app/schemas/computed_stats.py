"""Pydantic schemas for computed advanced stats, career, and shooting tracking."""

from decimal import Decimal

from pydantic import BaseModel


class ComputedAdvancedStats(BaseModel):
    """Computed advanced metrics (PER, BPM, Win Shares)."""

    per: Decimal | None
    obpm: Decimal | None
    dbpm: Decimal | None
    bpm: Decimal | None
    vorp: Decimal | None
    ows: Decimal | None
    dws: Decimal | None
    ws: Decimal | None
    ws_per_48: Decimal | None


class RadarData(BaseModel):
    """Radar chart percentile values for player profile visualization."""

    scoring: int | None
    playmaking: int | None
    defense: int | None
    efficiency: int | None
    volume: int | None
    durability: int | None
    clutch: int | None
    versatility: int | None


class PlayerComputedStatsResponse(BaseModel):
    """Full computed stats response for a player."""

    id: int
    nba_id: int
    name: str
    position: str | None
    team_abbreviation: str | None
    season: str
    computed: ComputedAdvancedStats | None
    radar: RadarData | None

    class Config:
        from_attributes = True


class CareerSeason(BaseModel):
    """Stats for a single season in a player's career."""

    season: str
    team_abbreviation: str | None
    games_played: int | None
    minutes: Decimal | None
    ppg: Decimal | None
    rpg: Decimal | None
    apg: Decimal | None
    spg: Decimal | None
    bpg: Decimal | None
    fg_pct: Decimal | None
    fg3_pct: Decimal | None
    ft_pct: Decimal | None


class PlayerCareerResponse(BaseModel):
    """Career trajectory response for a player."""

    id: int
    nba_id: int
    name: str
    position: str | None
    team_abbreviation: str | None
    seasons: list[CareerSeason]

    class Config:
        from_attributes = True


class ShootingTrackingStats(BaseModel):
    """Catch-and-shoot, pull-up, and drive tracking stats."""

    catch_shoot_fgm: Decimal | None
    catch_shoot_fga: Decimal | None
    catch_shoot_fg_pct: Decimal | None
    catch_shoot_fg3_pct: Decimal | None
    catch_shoot_pts: Decimal | None
    catch_shoot_efg_pct: Decimal | None
    pullup_fgm: Decimal | None
    pullup_fga: Decimal | None
    pullup_fg_pct: Decimal | None
    pullup_fg3_pct: Decimal | None
    pullup_pts: Decimal | None
    pullup_efg_pct: Decimal | None
    drives: Decimal | None
    drive_fgm: Decimal | None
    drive_fga: Decimal | None
    drive_fg_pct: Decimal | None
    drive_pts: Decimal | None
    drive_ast: Decimal | None
    drive_tov: Decimal | None


class PlayerShootingTrackingResponse(BaseModel):
    """Shooting tracking response for a player."""

    id: int
    nba_id: int
    name: str
    position: str | None
    team_abbreviation: str | None
    season: str
    shooting: ShootingTrackingStats | None

    class Config:
        from_attributes = True
