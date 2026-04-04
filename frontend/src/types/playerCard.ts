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

export interface ApiCardContextualized {
  raw_net_rtg: string | null
  contextualized_net_rtg: string | null
  percentile: number | null
}

export interface ApiCardImpact {
  on_off: ApiCardOnOff | null
  contextualized: ApiCardContextualized | null
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

export interface ApiCardDefensive {
  overall: ApiCardDefenseZone | null
  rim: ApiCardDefenseZone | null
  three_point: ApiCardDefenseZone | null
  iso_defense: ApiCardIsoDefense | null
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
}
