export interface PlayerMetrics {
  offensive_metric: number | null
  defensive_metric: number | null
  overall_metric: number | null
  offensive_percentile: number | null
  defensive_percentile: number | null
  composite_score?: number | null
  composite_rank?: number | null
  category_scores?: Record<string, number> | null
}

export interface PlayerTrackingStats {
  touches: number | null
  points_per_touch: number | null
  time_of_possession: number | null
  deflections: number | null
  contested_shots: number | null
}

export interface Player {
  id: number
  nba_id: number
  name: string
  position: string | null
  team_abbreviation: string | null
  metrics: PlayerMetrics | null
}

export interface PlayerPerGameStats {
  id: number
  nba_id: number
  name: string
  position: string | null
  team_abbreviation: string | null
  games_played: number | null
  ppg: number | null
  rpg: number | null
  apg: number | null
  mpg: number | null
  spg: number | null
  bpg: number | null
}

export interface PlayerDetail extends Player {
  season: string
  games_played: number | null
  tracking_stats: PlayerTrackingStats | null
}

export interface GameLog {
  game_date: string | null
  matchup: string | null
  wl: string | null
  minutes: number | null
  points: number | null
  rebounds: number | null
  assists: number | null
  steals: number | null
  blocks: number | null
  turnovers: number | null
  fgm: number | null
  fga: number | null
  fg_pct: number | null
  fg3m: number | null
  fg3a: number | null
  fg3_pct: number | null
  ftm: number | null
  fta: number | null
  ft_pct: number | null
  plus_minus: number | null
  game_score: number | null
  offensive_rebounds: number | null
  defensive_rebounds: number | null
}

export interface PlayerCardOption {
  id: number
  name: string
  position: string | null
  team_abbreviation: string | null
  season: string
}
