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
    handoff: CardPlayType | None = None


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
    # 1-indexed league rank by rapm_defense among qualified players
    # (>= 500 total minutes this season). None if player doesn't qualify.
    rank: int | None = None


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
    # EPM proxy sourced from DarkoHistory.dpm for the matching season year.
    # DARKO season convention: season string "2022-23" maps to integer year 2023.
    epm: Decimal | None = None


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


class CardTeammateDependency(BaseModel):
    """On-court net rating splits by teammate context.

    Aggregates the player's 5-man lineup net ratings into buckets defined
    by teammate attributes (spacers / rim protectors). Each bucket is a
    minutes-weighted average of net_rating across lineups that match the
    bucket criterion, with total bucket minutes reported for reliability.

    Values are `None` when the bucket has insufficient minutes (< 50) to
    be meaningful.
    """

    elite_spacing_net_rtg: Decimal | None = None
    elite_spacing_minutes: Decimal | None = None
    poor_spacing_net_rtg: Decimal | None = None
    poor_spacing_minutes: Decimal | None = None
    spacing_delta: Decimal | None = None
    with_rim_protector_net_rtg: Decimal | None = None
    with_rim_protector_minutes: Decimal | None = None
    without_rim_protector_net_rtg: Decimal | None = None
    without_rim_protector_minutes: Decimal | None = None


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
    teammate_dependency: CardTeammateDependency | None = None


class CardChampionshipPillar(BaseModel):
    name: str
    score: Decimal | None = None
    weight: Decimal | None = None


class CardPlayoffProjection(BaseModel):
    projected_ppg: Decimal | None = None
    projected_ts: Decimal | None = None
    reg_ppg: Decimal | None = None
    reg_ts: Decimal | None = None
    # Assists are historically stable reg->playoffs: projected_ast == reg_ast.
    projected_ast: Decimal | None = None
    reg_ast: Decimal | None = None
    # DRtg is historically stable reg->playoffs; pass-through from advanced stats.
    projected_drtg: Decimal | None = None
    reg_drtg: Decimal | None = None


class CardChampionship(BaseModel):
    index: Decimal | None = None
    tier: str | None = None
    win_probability: Decimal | None = None
    multiplier_vs_base: Decimal | None = None
    pillars: list[CardChampionshipPillar] = []
    playoff_projection: CardPlayoffProjection | None = None


class CardSpeedDistance(BaseModel):
    dist_miles: Decimal | None = None
    dist_miles_off: Decimal | None = None
    dist_miles_def: Decimal | None = None
    avg_speed: Decimal | None = None
    avg_speed_off: Decimal | None = None
    avg_speed_def: Decimal | None = None


class CardPassing(BaseModel):
    passes_made: Decimal | None = None
    passes_received: Decimal | None = None
    secondary_ast: Decimal | None = None
    potential_ast: Decimal | None = None
    ast_points_created: Decimal | None = None
    ast_adj: Decimal | None = None
    ast_to_pass_pct: Decimal | None = None
    ast_to_pass_pct_adj: Decimal | None = None


class CardReboundingTracking(BaseModel):
    oreb_contest_pct: Decimal | None = None
    oreb_chance_pct: Decimal | None = None
    oreb_chance_pct_adj: Decimal | None = None
    avg_oreb_dist: Decimal | None = None
    dreb_contest_pct: Decimal | None = None
    dreb_chance_pct: Decimal | None = None
    dreb_chance_pct_adj: Decimal | None = None
    avg_dreb_dist: Decimal | None = None
    reb_contest_pct: Decimal | None = None
    reb_chance_pct: Decimal | None = None
    reb_chance_pct_adj: Decimal | None = None


class CardDefenderDistanceEntry(BaseModel):
    range: str
    fga_freq: Decimal | None = None
    fg_pct: Decimal | None = None
    efg_pct: Decimal | None = None
    fg3_pct: Decimal | None = None


class CardDefensivePlayType(BaseModel):
    poss: int | None = None
    ppp: Decimal | None = None
    fg_pct: Decimal | None = None
    tov_pct: Decimal | None = None
    freq: Decimal | None = None
    percentile: Decimal | None = None


class CardTouchKind(BaseModel):
    touches: Decimal | None = None
    fga: Decimal | None = None
    fg_pct: Decimal | None = None
    fta: Decimal | None = None
    pts: Decimal | None = None
    passes: Decimal | None = None
    ast: Decimal | None = None
    tov: Decimal | None = None
    fouls: Decimal | None = None
    pts_per_touch: Decimal | None = None


class CardTouchesBreakdown(BaseModel):
    elbow: CardTouchKind | None = None
    post: CardTouchKind | None = None
    paint: CardTouchKind | None = None


class CardOpponentShootingBucket(BaseModel):
    label: str
    defended_fga: Decimal | None = None
    defended_fg_pct: Decimal | None = None
    normal_fg_pct: Decimal | None = None
    pct_plusminus: Decimal | None = None


class CardOpponentShooting(BaseModel):
    games: int | None = None
    buckets: list[CardOpponentShootingBucket] = []


class CardDefensivePlayTypes(BaseModel):
    isolation: CardDefensivePlayType | None = None
    pnr_ball_handler: CardDefensivePlayType | None = None
    post_up: CardDefensivePlayType | None = None
    spot_up: CardDefensivePlayType | None = None
    transition: CardDefensivePlayType | None = None


class CardGameLog(BaseModel):
    game_date: str | None = None
    matchup: str | None = None
    wl: str | None = None
    minutes: Decimal | None = None
    pts: int | None = None
    reb: int | None = None
    ast: int | None = None
    stl: int | None = None
    blk: int | None = None
    tov: int | None = None
    fg_pct: Decimal | None = None
    fg3_pct: Decimal | None = None
    plus_minus: int | None = None
    game_score: Decimal | None = None


class CardConsistency(BaseModel):
    games_used: int | None = None
    pts_cv: Decimal | None = None
    ast_cv: Decimal | None = None
    reb_cv: Decimal | None = None
    game_score_cv: Decimal | None = None
    game_score_avg: Decimal | None = None
    game_score_std: Decimal | None = None
    game_score_max: Decimal | None = None
    game_score_min: Decimal | None = None
    boom_games: int | None = None
    bust_games: int | None = None
    boom_pct: Decimal | None = None
    bust_pct: Decimal | None = None
    best_streak: int | None = None
    worst_streak: int | None = None
    dd_rate: Decimal | None = None
    td_rate: Decimal | None = None
    consistency_score: int | None = None


class CardFrictionEfficiency(BaseModel):
    """TS/eFG by defender proximity + a single "friction slope" summary.

    Slope = wide_open_efg - very_tight_efg. Positive means efficiency
    collapses under pressure (big drop from wide-open to contested);
    near zero means the player shoots roughly the same regardless of
    coverage. Built directly from PlayerDefenderDistanceShooting.
    """

    very_tight_efg: Decimal | None = None
    tight_efg: Decimal | None = None
    open_efg: Decimal | None = None
    wide_open_efg: Decimal | None = None
    friction_slope: Decimal | None = None
    pressure_adjusted_efg: Decimal | None = None


class CardGravityIndex(BaseModel):
    """Approximate player gravity using defender-proximity + on/off lift.

    NBA Stats does not expose teammate catch-and-shoot defender distance
    filtered by focal-player on/off, so we proxy gravity via:
    - tight_attention_rate: share of the player's own FGA with a defender
      within 4 ft (very_tight + tight freq). Defenses assign tighter
      coverage to higher-gravity players.
    - team_off_lift: on_court_off_rating - off_court_off_rating. Team
      offense improving when the player is on hints at gravity spillover.
    Index is a 0-100 composite of both signals.
    """

    tight_attention_rate: Decimal | None = None
    team_off_lift: Decimal | None = None
    gravity_index: Decimal | None = None


class CardShotDiet(BaseModel):
    """Shannon entropy over the player's offensive play-type frequencies.

    entropy_normalized ranges 0 (single-mode) to 1 (uniform across all
    play types). primary_modes counts play types with >= 10% frequency;
    top_play_type / top_freq identify the dominant mode.
    """

    entropy: Decimal | None = None
    entropy_normalized: Decimal | None = None
    primary_modes: int | None = None
    top_play_type: str | None = None
    top_play_type_freq: Decimal | None = None


class CardRimGravity(BaseModel):
    """How much the player bends the defense toward the rim.

    Composite of paint-touch volume, drive volume, rim FG% vs. league
    avg, and paint-touch pts/touch. Scored 0-100.
    """

    paint_touches_per_game: Decimal | None = None
    drives_per_game: Decimal | None = None
    rim_fg_pct: Decimal | None = None
    rim_fg_pct_vs_league: Decimal | None = None
    paint_pts_per_touch: Decimal | None = None
    rim_gravity_score: Decimal | None = None


class CardPassFunnel(BaseModel):
    """Creation funnel: passes -> potential assists -> actual assists.

    Conversion rates expose whether a high-assist player is truly
    creating or just hub-passing. cascade_rate (secondary_ast / passes)
    captures chain playmaking (your pass starts an action that assists
    the next).
    """

    passes_made: Decimal | None = None
    potential_ast: Decimal | None = None
    ast: Decimal | None = None
    secondary_ast: Decimal | None = None
    pass_to_potential_pct: Decimal | None = None
    potential_to_actual_pct: Decimal | None = None
    pass_to_actual_pct: Decimal | None = None
    cascade_rate: Decimal | None = None


class CardLeverageTs(BaseModel):
    """TS% in high-leverage games vs overall, stripping blowouts.

    A game counts as "leverage" when |plus_minus| <= 15 — a rough
    garbage-time filter applied at game granularity. Reported deltas
    highlight players who step up (or fade) in meaningful minutes.
    """

    overall_ts_pct: Decimal | None = None
    leverage_ts_pct: Decimal | None = None
    blowout_ts_pct: Decimal | None = None
    ts_leverage_delta: Decimal | None = None
    leverage_games: int | None = None
    blowout_games: int | None = None


class CardPossessionDwell(BaseModel):
    """How efficiently a player converts ball-holding time into offense.

    Combines touches + time-of-possession from season totals. A low
    dwell ratio with high pts/sec signals a quick-decision creator; a
    high dwell with low pts/sec signals iso-heavy or hesitant usage.
    """

    avg_sec_per_touch: Decimal | None = None
    pts_per_touch: Decimal | None = None
    pts_per_second: Decimal | None = None
    creation_per_second: Decimal | None = None
    dwell_efficiency_score: Decimal | None = None


class CardMileProduction(BaseModel):
    """Offensive output per mile traveled on the court.

    Rewards efficient movement — high-usage-but-stationary scorers
    score low here, while guards who cover ground to set up offense
    score higher. Also reports offensive distance share for context.
    """

    dist_miles_per_game: Decimal | None = None
    dist_miles_off_share: Decimal | None = None
    pts_ast_per_game: Decimal | None = None
    production_per_mile: Decimal | None = None
    production_per_off_mile: Decimal | None = None


class CardLateSeasonTrend(BaseModel):
    """Last-N games vs first-N games trend — fatigue/engagement proxy.

    Not a literal Q4 vs Q1 split (NBA Stats does not expose per-quarter
    tracking at the ingest layer). Uses GameStats game_score to compare
    the player's play at the season's tail vs. its start. Positive
    delta = late-season surge; negative = late-season fade.
    """

    early_games: int | None = None
    late_games: int | None = None
    early_game_score: Decimal | None = None
    late_game_score: Decimal | None = None
    trend_delta: Decimal | None = None
    early_minutes_avg: Decimal | None = None
    late_minutes_avg: Decimal | None = None


class CardDefensiveTerrain(BaseModel):
    """Weighted defensive stopping-power map across rim / mid / 3PT.

    Each zone's contribution = frequency × (-pct_plusminus) — larger is
    better because opponents shooting below their normal FG% is a win
    for the defender. Mid-range frequency is inferred as whatever
    overall coverage is left after rim + 3PT.
    """

    rim_freq: Decimal | None = None
    rim_plus_minus: Decimal | None = None
    rim_contribution: Decimal | None = None
    mid_freq: Decimal | None = None
    mid_plus_minus: Decimal | None = None
    mid_contribution: Decimal | None = None
    three_freq: Decimal | None = None
    three_plus_minus: Decimal | None = None
    three_contribution: Decimal | None = None
    terrain_score: Decimal | None = None


class CardContestConversion(BaseModel):
    """How often a defender's contests translate to forced misses.

    Contests from SeasonStats (all shots contested) paired with
    defended FGA / FGM (shots where the player was nearest defender).
    Scope mismatch is noted in the UI — contests include help-side
    work, while defended FGA only counts primary-defender shots.
    """

    contests_per_game: Decimal | None = None
    defended_fga_per_game: Decimal | None = None
    misses_forced_per_game: Decimal | None = None
    miss_rate: Decimal | None = None
    contest_to_miss_score: Decimal | None = None


class CardLineupBuoyancy(BaseModel):
    """Floor-raiser vs. ceiling-raiser signal from a player's lineups.

    Partitions all of the player's 5-man lineups by minutes-weighted
    net rating into a worst tercile (floor) and best tercile (ceiling),
    then reports the weighted-average NRtg of each. A high floor says
    the player stabilizes bad combos; a dominant ceiling says they
    amplify already-good combos. `buoyancy_type` summarizes the shape.
    """

    total_lineups: int | None = None
    qualifying_minutes: Decimal | None = None
    worst_tercile_net_rtg: Decimal | None = None
    worst_tercile_minutes: Decimal | None = None
    best_tercile_net_rtg: Decimal | None = None
    best_tercile_minutes: Decimal | None = None
    median_lineup_net_rtg: Decimal | None = None
    lineup_spread: Decimal | None = None
    floor_score: Decimal | None = None
    ceiling_score: Decimal | None = None
    buoyancy_type: str | None = None


class CardSchemeRobustness(BaseModel):
    """Scheme-collapse risk from PPP variance across the top play types.

    Takes the player's top-3 play types by frequency (min 25 possessions
    each) and computes the coefficient of variation of their PPPs.
    Tight cluster of high PPPs = scheme-proof scorer. Wide spread = one
    or two modes carry them; the rest collapse under a scheme change.
    """

    top_play_types: list[str] = []
    top_play_type_ppps: list[Decimal] = []
    ppp_mean: Decimal | None = None
    ppp_std: Decimal | None = None
    coefficient_of_variation: Decimal | None = None
    collapse_risk_score: Decimal | None = None
    robustness_score: Decimal | None = None


class PlayerCardData(BaseModel):
    id: int
    nba_id: int
    name: str
    position: str | None = None
    team_abbreviation: str | None = None
    height: str | None = None
    weight: int | None = None
    jersey_number: str | None = None
    age: str | None = None
    country: str | None = None
    draft_year: int | None = None
    draft_round: int | None = None
    draft_number: int | None = None
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
    speed_distance: CardSpeedDistance | None = None
    passing: CardPassing | None = None
    rebounding_tracking: CardReboundingTracking | None = None
    defender_distance: list[CardDefenderDistanceEntry] = []
    touches_breakdown: CardTouchesBreakdown | None = None
    opponent_shooting: CardOpponentShooting | None = None
    defensive_play_types: CardDefensivePlayTypes | None = None
    recent_games: list[CardGameLog] = []
    consistency: CardConsistency | None = None
    friction_efficiency: CardFrictionEfficiency | None = None
    gravity_index: CardGravityIndex | None = None
    shot_diet: CardShotDiet | None = None
    rim_gravity: CardRimGravity | None = None
    pass_funnel: CardPassFunnel | None = None
    leverage_ts: CardLeverageTs | None = None
    possession_dwell: CardPossessionDwell | None = None
    mile_production: CardMileProduction | None = None
    late_season_trend: CardLateSeasonTrend | None = None
    defensive_terrain: CardDefensiveTerrain | None = None
    contest_conversion: CardContestConversion | None = None
    lineup_buoyancy: CardLineupBuoyancy | None = None
    scheme_robustness: CardSchemeRobustness | None = None
