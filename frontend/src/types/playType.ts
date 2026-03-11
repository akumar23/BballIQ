export interface PlayTypeMetrics {
  possessions: number | null
  points: number | null
  ppp: number | null
  fg_pct: number | null
  frequency: number | null
  ppp_percentile: number | null
}

export interface SpotUpMetrics extends PlayTypeMetrics {
  fg3m: number | null
  fg3a: number | null
  fg3_pct: number | null
}

export interface PlayerPlayTypeStats {
  id: number
  nba_id: number
  name: string
  position: string | null
  team_abbreviation: string | null
  season: string
  total_poss: number | null
  isolation: PlayTypeMetrics | null
  pnr_ball_handler: PlayTypeMetrics | null
  pnr_roll_man: PlayTypeMetrics | null
  post_up: PlayTypeMetrics | null
  spot_up: SpotUpMetrics | null
  transition: PlayTypeMetrics | null
  cut: PlayTypeMetrics | null
  off_screen: PlayTypeMetrics | null
}

export interface PlayTypeLeaderboardEntry {
  rank: number | null
  id: number
  nba_id: number
  name: string
  position: string | null
  team_abbreviation: string | null
  possessions: number | null
  points: number | null
  ppp: number | null
  fg_pct: number | null
  frequency: number | null
  ppp_percentile: number | null
}

export interface PlayTypeLeaderboardResponse {
  play_type: string
  sort_by: string
  entries: PlayTypeLeaderboardEntry[]
}

export type PlayTypeKey =
  | 'isolation'
  | 'pnr_ball_handler'
  | 'pnr_roll_man'
  | 'post_up'
  | 'spot_up'
  | 'transition'
  | 'cut'
  | 'off_screen'

export type PlayTypeSortBy = 'ppp' | 'possessions' | 'fg_pct' | 'frequency'

export const PLAY_TYPE_LABELS: Record<PlayTypeKey, string> = {
  isolation: 'Isolation',
  pnr_ball_handler: 'PnR Ball Handler',
  pnr_roll_man: 'PnR Roll Man',
  post_up: 'Post-Up',
  spot_up: 'Spot-Up',
  transition: 'Transition',
  cut: 'Cut',
  off_screen: 'Off Screen',
}

export const SORT_BY_LABELS: Record<PlayTypeSortBy, string> = {
  ppp: 'PPP',
  possessions: 'Possessions',
  fg_pct: 'FG%',
  frequency: 'Frequency',
}
