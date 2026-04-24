/** API response types for GET /api/players/{id}/card */

export interface ApiCardTraditional {
  ppg: string | null
  rpg: string | null
  apg: string | null
  spg: string | null
  bpg: string | null
  tov: string | null
  fg_pct: string | null
  fg3_pct: string | null
  ft_pct: string | null
  mpg: string | null
  games_played: number | null
}

export interface ApiCardAdvanced {
  per: string | null
  ts_pct: string | null
  ws48: string | null
  bpm: string | null
  vorp: string | null
  ortg: string | null
  drtg: string | null
  usg_pct: string | null
  ows: string | null
  dws: string | null
}

export interface ApiCardOnOff {
  on_ortg: string | null
  off_ortg: string | null
  on_drtg: string | null
  off_drtg: string | null
  net_swing: string | null
}

export interface ApiCardAdjustmentStep {
  name: string
  value: string | null
  cumulative: string | null
  explanation: string
}

export interface ApiCardContextualized {
  raw_net_rtg: string | null
  contextualized_net_rtg: string | null
  percentile: number | null
  adjustments: ApiCardAdjustmentStep[]
}

export interface ApiCardLineup {
  players: string[]
  minutes: string | null
  raw_net: string | null
  ctx_net: string | null
  opp_tier: string
}

export interface ApiCardWithoutTeammate {
  teammate: string
  net_rtg: string | null
  minutes: string | null
}

export interface ApiCardLineupContext {
  top_lineups: ApiCardLineup[]
  without_top_teammate: ApiCardWithoutTeammate | null
}

export interface ApiCardImpact {
  on_off: ApiCardOnOff | null
  contextualized: ApiCardContextualized | null
  actual_wins: number | null
}

export interface ApiCardPlayType {
  possessions: string | null
  ppp: string | null
  fg_pct: string | null
  frequency: string | null
  ppp_percentile: number | null
}

export interface ApiCardShotZone {
  zone: string
  fga_per_game: string | null
  fg_pct: string | null
  freq: string | null
  league_avg: string | null
}

export interface ApiCardDefenseZone {
  d_fg_pct: string | null
  normal_fg_pct: string | null
  pct_plusminus: string | null
}

export interface ApiCardIsoDefense {
  poss: number | null
  ppp: string | null
  fg_pct: string | null
  percentile: number | null
}

export interface ApiCardDefenseOverview {
  contest_rate: string | null
  stl_rate: string | null
  blk_rate: string | null
  deflections_per_game: string | null
  rim_contests_per_game: string | null
  /** 1-indexed league rank by RAPM defense among qualified players. */
  rank: number | null
}

export interface ApiCardDefensive {
  overall: ApiCardDefenseZone | null
  rim: ApiCardDefenseZone | null
  three_point: ApiCardDefenseZone | null
  iso_defense: ApiCardIsoDefense | null
  overview: ApiCardDefenseOverview | null
}

export interface ApiCardRadar {
  scoring: number | null
  playmaking: number | null
  defense: number | null
  efficiency: number | null
  volume: number | null
  durability: number | null
  clutch: number | null
  versatility: number | null
}

export interface ApiCardCareerSeason {
  season: string
  ppg: string | null
  rpg: string | null
  apg: string | null
  fg_pct: string | null
  fg3_pct: string | null
  ft_pct: string | null
  minutes: string | null
  games_played: number | null
  per: string | null
  ws48: string | null
  bpm: string | null
  /** Per-season EPM proxy (DARKO DPM for the matching year). */
  epm: string | null
}

export interface ApiCardPlayoffProjection {
  projected_ppg: string | null
  projected_ts: string | null
  reg_ppg: string | null
  reg_ts: string | null
  projected_ast: string | null
  reg_ast: string | null
  projected_drtg: string | null
  reg_drtg: string | null
}

export interface ApiCardAllInOne {
  rapm: string | null
  rapm_offense: string | null
  rapm_defense: string | null
  rpm: string | null
  rpm_offense: string | null
  rpm_defense: string | null
  epm: string | null
  epm_offense: string | null
  epm_defense: string | null
  lebron: string | null
  lebron_offense: string | null
  lebron_defense: string | null
  darko: string | null
  darko_offense: string | null
  darko_defense: string | null
  laker: string | null
  laker_offense: string | null
  laker_defense: string | null
  mamba: string | null
  mamba_offense: string | null
  mamba_defense: string | null
}

export interface ApiCardMatchup {
  opponent: string
  possessions: string | null
  dfg_pct: string | null
  pts_allowed: string | null
}

export interface ApiCardLuckAdjusted {
  x_wins: string | null
  clutch_epa: string | null
  clutch_epa_per_game: string | null
  garbage_time_ppg: string | null
}

export interface ApiCardOpponentTierEntry {
  tier: string
  possessions: number | null
  dfg_pct: string | null
  ppp_allowed: string | null
  weight: string | null
}

export interface ApiCardSchemeScore {
  scheme: string
  fit_score: string | null
}

export interface ApiCardTeammateDependency {
  elite_spacing_net_rtg: string | null
  elite_spacing_minutes: string | null
  poor_spacing_net_rtg: string | null
  poor_spacing_minutes: string | null
  spacing_delta: string | null
  with_rim_protector_net_rtg: string | null
  with_rim_protector_minutes: string | null
  without_rim_protector_net_rtg: string | null
  without_rim_protector_minutes: string | null
}

export interface ApiCardPortability {
  index: string | null
  grade: string | null
  self_creation: string | null
  scheme_flexibility: string | null
  switchability: string | null
  low_dependency: string | null
  unassisted_rate_score: string | null
  self_created_ppp_score: string | null
  gravity_score: string | null
  creation_volume_score: string | null
  positions_guarded: Record<string, string | null> | null
  scheme_scores: ApiCardSchemeScore[]
  teammate_dependency: ApiCardTeammateDependency | null
}

export interface ApiCardChampionshipPillar {
  name: string
  score: string | null
  weight: string | null
}

export interface ApiCardChampionship {
  index: string | null
  tier: string | null
  win_probability: string | null
  multiplier_vs_base: string | null
  pillars: ApiCardChampionshipPillar[]
  playoff_projection: ApiCardPlayoffProjection | null
}

export interface ApiCardPlayTypes {
  isolation: ApiCardPlayType | null
  pnr_ball_handler: ApiCardPlayType | null
  pnr_roll_man: ApiCardPlayType | null
  post_up: ApiCardPlayType | null
  spot_up: ApiCardPlayType | null
  transition: ApiCardPlayType | null
  cut: ApiCardPlayType | null
  off_screen: ApiCardPlayType | null
  handoff: ApiCardPlayType | null
}

export interface ApiCardTouchKind {
  touches: string | null
  fga: string | null
  fg_pct: string | null
  fta: string | null
  pts: string | null
  passes: string | null
  ast: string | null
  tov: string | null
  fouls: string | null
  pts_per_touch: string | null
}

export interface ApiCardTouchesBreakdown {
  elbow: ApiCardTouchKind | null
  post: ApiCardTouchKind | null
  paint: ApiCardTouchKind | null
}

export interface ApiCardOpponentShootingBucket {
  label: string
  defended_fga: string | null
  defended_fg_pct: string | null
  normal_fg_pct: string | null
  pct_plusminus: string | null
}

export interface ApiCardOpponentShooting {
  games: number | null
  buckets: ApiCardOpponentShootingBucket[]
}

export interface PlayerCardData {
  id: number
  nba_id: number
  name: string
  position: string | null
  team_abbreviation: string | null
  height: string | null
  height_inches: number | null
  weight: number | null
  jersey_number: string | null
  age: string | null
  country: string | null
  college: string | null
  draft_year: number | null
  draft_round: number | null
  draft_number: number | null
  season: string
  traditional: ApiCardTraditional | null
  advanced: ApiCardAdvanced | null
  radar: ApiCardRadar | null
  impact: ApiCardImpact | null
  play_types: ApiCardPlayTypes | null
  shot_zones: ApiCardShotZone[]
  defensive: ApiCardDefensive | null
  career: ApiCardCareerSeason[]
  all_in_one: ApiCardAllInOne | null
  matchup_log: ApiCardMatchup[]
  luck_adjusted: ApiCardLuckAdjusted | null
  opponent_tiers: ApiCardOpponentTierEntry[]
  scheme_compatibility: ApiCardSchemeScore[]
  portability: ApiCardPortability | null
  championship: ApiCardChampionship | null
  lineup_context: ApiCardLineupContext | null
  speed_distance: ApiCardSpeedDistance | null
  passing: ApiCardPassing | null
  rebounding_tracking: ApiCardReboundingTracking | null
  defender_distance: ApiCardDefenderDistanceEntry[]
  touches_breakdown: ApiCardTouchesBreakdown | null
  opponent_shooting: ApiCardOpponentShooting | null
  defensive_play_types: ApiCardDefensivePlayTypes | null
  recent_games: ApiCardGameLog[]
  consistency: ApiCardConsistency | null
  friction_efficiency: ApiCardFrictionEfficiency | null
  gravity_index: ApiCardGravityIndex | null
  shot_diet: ApiCardShotDiet | null
  rim_gravity: ApiCardRimGravity | null
  pass_funnel: ApiCardPassFunnel | null
  leverage_ts: ApiCardLeverageTs | null
  possession_dwell: ApiCardPossessionDwell | null
  mile_production: ApiCardMileProduction | null
  late_season_trend: ApiCardLateSeasonTrend | null
  defensive_terrain: ApiCardDefensiveTerrain | null
  contest_conversion: ApiCardContestConversion | null
  lineup_buoyancy: ApiCardLineupBuoyancy | null
  scheme_robustness: ApiCardSchemeRobustness | null
}

export interface ApiCardGameLog {
  game_date: string | null
  matchup: string | null
  wl: string | null
  minutes: string | null
  pts: number | null
  reb: number | null
  ast: number | null
  stl: number | null
  blk: number | null
  tov: number | null
  fg_pct: string | null
  fg3_pct: string | null
  plus_minus: number | null
  game_score: string | null
}

export interface ApiCardConsistency {
  games_used: number | null
  pts_cv: string | null
  ast_cv: string | null
  reb_cv: string | null
  game_score_cv: string | null
  game_score_avg: string | null
  game_score_std: string | null
  game_score_max: string | null
  game_score_min: string | null
  boom_games: number | null
  bust_games: number | null
  boom_pct: string | null
  bust_pct: string | null
  best_streak: number | null
  worst_streak: number | null
  dd_rate: string | null
  td_rate: string | null
  consistency_score: number | null
}

export interface ApiCardSpeedDistance {
  dist_miles: string | null
  dist_miles_off: string | null
  dist_miles_def: string | null
  avg_speed: string | null
  avg_speed_off: string | null
  avg_speed_def: string | null
}

export interface ApiCardPassing {
  passes_made: string | null
  passes_received: string | null
  secondary_ast: string | null
  potential_ast: string | null
  ast_points_created: string | null
  ast_adj: string | null
  ast_to_pass_pct: string | null
  ast_to_pass_pct_adj: string | null
}

export interface ApiCardReboundingTracking {
  oreb_contest_pct: string | null
  oreb_chance_pct: string | null
  oreb_chance_pct_adj: string | null
  avg_oreb_dist: string | null
  dreb_contest_pct: string | null
  dreb_chance_pct: string | null
  dreb_chance_pct_adj: string | null
  avg_dreb_dist: string | null
  reb_contest_pct: string | null
  reb_chance_pct: string | null
  reb_chance_pct_adj: string | null
}

export interface ApiCardDefenderDistanceEntry {
  range: string
  fga_freq: string | null
  fg_pct: string | null
  efg_pct: string | null
  fg3_pct: string | null
  fg2a_freq: string | null
  fg2_pct: string | null
  fg3a_freq: string | null
}

export interface ApiCardDefensivePlayType {
  poss: number | null
  ppp: string | null
  fg_pct: string | null
  tov_pct: string | null
  freq: string | null
  percentile: string | null
}

export interface ApiCardDefensivePlayTypes {
  isolation: ApiCardDefensivePlayType | null
  pnr_ball_handler: ApiCardDefensivePlayType | null
  post_up: ApiCardDefensivePlayType | null
  spot_up: ApiCardDefensivePlayType | null
  transition: ApiCardDefensivePlayType | null
}

export interface ApiCardFrictionEfficiency {
  very_tight_efg: string | null
  tight_efg: string | null
  open_efg: string | null
  wide_open_efg: string | null
  friction_slope: string | null
  pressure_adjusted_efg: string | null
}

export interface ApiCardGravityIndex {
  tight_attention_rate: string | null
  team_off_lift: string | null
  gravity_index: string | null
}

export interface ApiCardShotDiet {
  entropy: string | null
  entropy_normalized: string | null
  primary_modes: number | null
  top_play_type: string | null
  top_play_type_freq: string | null
}

export interface ApiCardRimGravity {
  paint_touches_per_game: string | null
  drives_per_game: string | null
  rim_fg_pct: string | null
  rim_fg_pct_vs_league: string | null
  paint_pts_per_touch: string | null
  rim_gravity_score: string | null
}

export interface ApiCardPassFunnel {
  passes_made: string | null
  potential_ast: string | null
  ast: string | null
  secondary_ast: string | null
  pass_to_potential_pct: string | null
  potential_to_actual_pct: string | null
  pass_to_actual_pct: string | null
  cascade_rate: string | null
}

export interface ApiCardLeverageTs {
  overall_ts_pct: string | null
  leverage_ts_pct: string | null
  blowout_ts_pct: string | null
  ts_leverage_delta: string | null
  leverage_games: number | null
  blowout_games: number | null
}

export interface ApiCardPossessionDwell {
  avg_sec_per_touch: string | null
  pts_per_touch: string | null
  pts_per_second: string | null
  creation_per_second: string | null
  dwell_efficiency_score: string | null
}

export interface ApiCardMileProduction {
  dist_miles_per_game: string | null
  dist_miles_off_share: string | null
  pts_ast_per_game: string | null
  production_per_mile: string | null
  production_per_off_mile: string | null
}

export interface ApiCardLateSeasonTrend {
  early_games: number | null
  late_games: number | null
  early_game_score: string | null
  late_game_score: string | null
  trend_delta: string | null
  early_minutes_avg: string | null
  late_minutes_avg: string | null
}

export interface ApiCardDefensiveTerrain {
  rim_freq: string | null
  rim_plus_minus: string | null
  rim_contribution: string | null
  mid_freq: string | null
  mid_plus_minus: string | null
  mid_contribution: string | null
  three_freq: string | null
  three_plus_minus: string | null
  three_contribution: string | null
  terrain_score: string | null
}

export interface ApiCardContestConversion {
  contests_per_game: string | null
  defended_fga_per_game: string | null
  misses_forced_per_game: string | null
  miss_rate: string | null
  contest_to_miss_score: string | null
}

export interface ApiCardLineupBuoyancy {
  total_lineups: number | null
  qualifying_minutes: string | null
  worst_tercile_net_rtg: string | null
  worst_tercile_minutes: string | null
  best_tercile_net_rtg: string | null
  best_tercile_minutes: string | null
  median_lineup_net_rtg: string | null
  lineup_spread: string | null
  floor_score: string | null
  ceiling_score: string | null
  buoyancy_type: string | null
}

export interface ApiCardSchemeRobustness {
  top_play_types: string[]
  top_play_type_ppps: string[]
  ppp_mean: string | null
  ppp_std: string | null
  coefficient_of_variation: string | null
  collapse_risk_score: string | null
  robustness_score: string | null
}
