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


class CardAdjustmentStep(BaseModel):
    name: str
    value: Decimal | None = None
    cumulative: Decimal | None = None
    explanation: str = ""


class CardContextualized(BaseModel):
    raw_net_rtg: Decimal | None = None
    contextualized_net_rtg: Decimal | None = None
    percentile: Decimal | None = None
    adjustments: list[CardAdjustmentStep] = []


class CardLineup(BaseModel):
    players: list[str] = []
    minutes: Decimal | None = None
    raw_net: Decimal | None = None
    ctx_net: Decimal | None = None
    opp_tier: str = ""


class CardWithoutTeammate(BaseModel):
    teammate: str = ""
    net_rtg: Decimal | None = None
    minutes: Decimal | None = None


class CardLineupContext(BaseModel):
    top_lineups: list[CardLineup] = []
    without_top_teammate: CardWithoutTeammate | None = None


class CardImpact(BaseModel):
    on_off: CardOnOff | None = None
    contextualized: CardContextualized | None = None
    actual_wins: int | None = None


class CardPlayType(BaseModel):
    possessions: Decimal | None = None
    ppp: Decimal | None = None
    fg_pct: Decimal | None = None
    frequency: Decimal | None = None
    ppp_percentile: Decimal | None = None


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
    percentile: Decimal | None = None


class CardDefenseOverview(BaseModel):
    contest_rate: Decimal | None = None
    stl_rate: Decimal | None = None
    blk_rate: Decimal | None = None
    deflections_per_game: Decimal | None = None
    rim_contests_per_game: Decimal | None = None


class CardDefensive(BaseModel):
    overall: CardDefenseZone | None = None
    rim: CardDefenseZone | None = None
    three_point: CardDefenseZone | None = None
    iso_defense: CardIsoDefense | None = None
    overview: CardDefenseOverview | None = None


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
    per: Decimal | None = None
    ws48: Decimal | None = None
    bpm: Decimal | None = None


class CardAllInOne(BaseModel):
    rapm: Decimal | None = None
    rapm_offense: Decimal | None = None
    rapm_defense: Decimal | None = None
    rpm: Decimal | None = None
    rpm_offense: Decimal | None = None
    rpm_defense: Decimal | None = None
    epm: Decimal | None = None
    epm_offense: Decimal | None = None
    epm_defense: Decimal | None = None
    lebron: Decimal | None = None
    lebron_offense: Decimal | None = None
    lebron_defense: Decimal | None = None
    darko: Decimal | None = None
    darko_offense: Decimal | None = None
    darko_defense: Decimal | None = None
    laker: Decimal | None = None
    laker_offense: Decimal | None = None
    laker_defense: Decimal | None = None
    mamba: Decimal | None = None
    mamba_offense: Decimal | None = None
    mamba_defense: Decimal | None = None


class CardMatchup(BaseModel):
    opponent: str
    possessions: Decimal | None = None
    dfg_pct: Decimal | None = None
    pts_allowed: Decimal | None = None


class CardLuckAdjusted(BaseModel):
    x_wins: Decimal | None = None
    clutch_epa: Decimal | None = None
    clutch_epa_per_game: Decimal | None = None
    garbage_time_ppg: Decimal | None = None


class CardOpponentTierEntry(BaseModel):
    tier: str
    possessions: int | None = None
    dfg_pct: Decimal | None = None
    ppp_allowed: Decimal | None = None
    weight: Decimal | None = None


class CardSchemeScore(BaseModel):
    scheme: str
    fit_score: Decimal | None = None


class CardPortability(BaseModel):
    index: Decimal | None = None
    grade: str | None = None
    self_creation: Decimal | None = None
    scheme_flexibility: Decimal | None = None
    switchability: Decimal | None = None
    low_dependency: Decimal | None = None
    unassisted_rate_score: Decimal | None = None
    self_created_ppp_score: Decimal | None = None
    gravity_score: Decimal | None = None
    creation_volume_score: Decimal | None = None
    positions_guarded: dict[str, Decimal | None] | None = None
    scheme_scores: list[CardSchemeScore] = []


class CardChampionshipPillar(BaseModel):
    name: str
    score: Decimal | None = None
    weight: Decimal | None = None


class CardPlayoffProjection(BaseModel):
    projected_ppg: Decimal | None = None
    projected_ts: Decimal | None = None
    reg_ppg: Decimal | None = None
    reg_ts: Decimal | None = None


class CardChampionship(BaseModel):
    index: Decimal | None = None
    tier: str | None = None
    win_probability: Decimal | None = None
    multiplier_vs_base: Decimal | None = None
    pillars: list[CardChampionshipPillar] = []
    playoff_projection: CardPlayoffProjection | None = None


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
    all_in_one: CardAllInOne | None = None
    matchup_log: list[CardMatchup] = []
    luck_adjusted: CardLuckAdjusted | None = None
    opponent_tiers: list[CardOpponentTierEntry] = []
    scheme_compatibility: list[CardSchemeScore] = []
    portability: CardPortability | None = None
    championship: CardChampionship | None = None
    lineup_context: CardLineupContext | None = None
