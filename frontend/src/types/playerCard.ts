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

export interface ApiCardPlayTypes {
  isolation: ApiCardPlayType | null
  pnr_ball_handler: ApiCardPlayType | null
  pnr_roll_man: ApiCardPlayType | null
  post_up: ApiCardPlayType | null
  spot_up: ApiCardPlayType | null
  transition: ApiCardPlayType | null
  cut: ApiCardPlayType | null
  off_screen: ApiCardPlayType | null
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
}

export interface ApiCardPlayoffProjection {
  projected_ppg: string | null
  projected_ts: string | null
  reg_ppg: string | null
  reg_ts: string | null
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
  raptor: string | null
  raptor_offense: string | null
  raptor_defense: string | null
  lebron: string | null
  lebron_offense: string | null
  lebron_defense: string | null
  darko: string | null
  darko_offense: string | null
  darko_defense: string | null
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

export interface PlayerCardData {
  id: number
  nba_id: number
  name: string
  position: string | null
  team_abbreviation: string | null
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
}
