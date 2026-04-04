"""Schemas for the player card endpoint — aggregates all available player data."""

from decimal import Decimal

from pydantic import BaseModel


class CardTraditional(BaseModel):
    ppg: Decimal | None = None
    rpg: Decimal | None = None
    apg: Decimal | None = None
    spg: Decimal | None = None
    bpg: Decimal | None = None
    tov: Decimal | None = None
    fg_pct: Decimal | None = None
    fg3_pct: Decimal | None = None
    ft_pct: Decimal | None = None
    mpg: Decimal | None = None
    games_played: int | None = None


class CardAdvanced(BaseModel):
    per: Decimal | None = None
    ts_pct: Decimal | None = None
    ws48: Decimal | None = None
    bpm: Decimal | None = None
    vorp: Decimal | None = None
    ortg: Decimal | None = None
    drtg: Decimal | None = None
    usg_pct: Decimal | None = None
    ows: Decimal | None = None
    dws: Decimal | None = None


class CardOnOff(BaseModel):
    on_ortg: Decimal | None = None
    off_ortg: Decimal | None = None
    on_drtg: Decimal | None = None
    off_drtg: Decimal | None = None
    net_swing: Decimal | None = None


class CardContextualized(BaseModel):
    raw_net_rtg: Decimal | None = None
    contextualized_net_rtg: Decimal | None = None
    percentile: int | None = None


class CardImpact(BaseModel):
    on_off: CardOnOff | None = None
    contextualized: CardContextualized | None = None


class CardPlayType(BaseModel):
    possessions: Decimal | None = None
    ppp: Decimal | None = None
    fg_pct: Decimal | None = None
    frequency: Decimal | None = None
    ppp_percentile: int | None = None


class CardPlayTypes(BaseModel):
    isolation: CardPlayType | None = None
    pnr_ball_handler: CardPlayType | None = None
    pnr_roll_man: CardPlayType | None = None
    post_up: CardPlayType | None = None
    spot_up: CardPlayType | None = None
    transition: CardPlayType | None = None
    cut: CardPlayType | None = None
    off_screen: CardPlayType | None = None


class CardShotZone(BaseModel):
    zone: str
    fga_per_game: Decimal | None = None
    fg_pct: Decimal | None = None
    freq: Decimal | None = None
    league_avg: Decimal | None = None


class CardDefenseZone(BaseModel):
    d_fg_pct: Decimal | None = None
    normal_fg_pct: Decimal | None = None
    pct_plusminus: Decimal | None = None


class CardIsoDefense(BaseModel):
    poss: int | None = None
    ppp: Decimal | None = None
    fg_pct: Decimal | None = None
    percentile: int | None = None


class CardDefensive(BaseModel):
    overall: CardDefenseZone | None = None
    rim: CardDefenseZone | None = None
    three_point: CardDefenseZone | None = None
    iso_defense: CardIsoDefense | None = None


class CardRadar(BaseModel):
    scoring: int | None = None
    playmaking: int | None = None
    defense: int | None = None
    efficiency: int | None = None
    volume: int | None = None
    durability: int | None = None
    clutch: int | None = None
    versatility: int | None = None


class CardCareerSeason(BaseModel):
    season: str
    ppg: Decimal | None = None
    rpg: Decimal | None = None
    apg: Decimal | None = None
    fg_pct: Decimal | None = None
    fg3_pct: Decimal | None = None
    ft_pct: Decimal | None = None
    minutes: Decimal | None = None
    games_played: int | None = None


class PlayerCardData(BaseModel):
    id: int
    nba_id: int
    name: str
    position: str | None = None
    team_abbreviation: str | None = None
    season: str
    traditional: CardTraditional | None = None
    advanced: CardAdvanced | None = None
    radar: CardRadar | None = None
    impact: CardImpact | None = None
    play_types: CardPlayTypes | None = None
    shot_zones: list[CardShotZone] = []
    defensive: CardDefensive | None = None
    career: list[CardCareerSeason] = []
