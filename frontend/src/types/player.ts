export interface PlayerMetrics {
  offensive_metric: number | null
  defensive_metric: number | null
  overall_metric: number | null
  offensive_percentile: number | null
  defensive_percentile: number | null
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

export interface PlayerDetail extends Player {
  season: string
  games_played: number | null
  tracking_stats: PlayerTrackingStats | null
}
