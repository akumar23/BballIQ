"""Pydantic schemas for advanced stats, shot zones, clutch, and defensive profiles."""

from decimal import Decimal

from pydantic import BaseModel


class AdvancedStats(BaseModel):
    """NBA.com advanced stats for a player."""

    ts_pct: Decimal | None
    efg_pct: Decimal | None
    usg_pct: Decimal | None
    off_rating: Decimal | None
    def_rating: Decimal | None
    net_rating: Decimal | None
    pace: Decimal | None
    pie: Decimal | None
    ast_pct: Decimal | None
    ast_to: Decimal | None
    oreb_pct: Decimal | None
    dreb_pct: Decimal | None
    reb_pct: Decimal | None


class ShotZone(BaseModel):
    """A single shot zone with player stats and league comparison."""

    zone: str
    fgm: Decimal | None
    fga: Decimal | None
    fg_pct: Decimal | None
    freq: Decimal | None  # frequency of attempts from this zone
    league_avg: Decimal | None  # league average FG% for this zone


class PlayerShotZones(BaseModel):
    """Shot zone distribution for a player."""

    id: int
    nba_id: int
    name: str
    position: str | None
    team_abbreviation: str | None
    season: str
    zones: list[ShotZone]

    class Config:
        from_attributes = True


class ClutchStats(BaseModel):
    """Clutch time stats (last 5 minutes, within 5 points)."""

    games_played: int | None
    minutes: Decimal | None
    pts: Decimal | None
    fgm: Decimal | None
    fga: Decimal | None
    fg_pct: Decimal | None
    fg3m: Decimal | None
    fg3a: Decimal | None
    fg3_pct: Decimal | None
    ftm: Decimal | None
    fta: Decimal | None
    ft_pct: Decimal | None
    ast: Decimal | None
    reb: Decimal | None
    stl: Decimal | None
    blk: Decimal | None
    tov: Decimal | None
    plus_minus: Decimal | None
    net_rating: Decimal | None


class DefenseZoneStats(BaseModel):
    """Defensive stats for a specific zone/category."""

    d_fgm: Decimal | None
    d_fga: Decimal | None
    d_fg_pct: Decimal | None
    normal_fg_pct: Decimal | None
    pct_plusminus: Decimal | None  # DFG% differential vs league


class IsoDefenseStats(BaseModel):
    """Isolation defense stats from Synergy."""

    poss: int | None
    pts: int | None
    fgm: int | None
    fga: int | None
    ppp: Decimal | None
    fg_pct: Decimal | None
    percentile: Decimal | None


class PlayerDefensiveProfile(BaseModel):
    """Complete defensive profile for a player."""

    id: int
    nba_id: int
    name: str
    position: str | None
    team_abbreviation: str | None
    season: str
    # Overall defense
    overall: DefenseZoneStats | None
    # Rim protection
    rim: DefenseZoneStats | None
    # 3PT defense
    three_point: DefenseZoneStats | None
    # Isolation defense
    iso_defense: IsoDefenseStats | None

    class Config:
        from_attributes = True


class PlayerAdvancedStatsResponse(BaseModel):
    """Full advanced stats response for a player."""

    id: int
    nba_id: int
    name: str
    position: str | None
    team_abbreviation: str | None
    season: str
    advanced: AdvancedStats | None
    clutch: ClutchStats | None

    class Config:
        from_attributes = True
