export interface OnOffStats {
  on_court_minutes: number | null
  on_court_net_rating: number | null
  on_court_off_rating: number | null
  on_court_def_rating: number | null
  off_court_minutes: number | null
  off_court_net_rating: number | null
  off_court_off_rating: number | null
  off_court_def_rating: number | null
  net_rating_diff: number | null
  off_rating_diff: number | null
  def_rating_diff: number | null
}

export interface ImpactContext {
  avg_teammate_net_rating: number | null
  teammate_adjustment: number | null
  pct_minutes_vs_starters: number | null
  opponent_quality_factor: number | null
  reliability_factor: number | null
}

export interface ImpactRating {
  raw_net_rating_diff: number | null
  raw_off_rating_diff: number | null
  raw_def_rating_diff: number | null
  contextualized_net_impact: number | null
  contextualized_off_impact: number | null
  contextualized_def_impact: number | null
  impact_percentile: number | null
  offensive_impact_percentile: number | null
  defensive_impact_percentile: number | null
}

export interface PlayerImpact {
  id: number
  nba_id: number
  name: string
  position: string | null
  team_abbreviation: string | null
  season: string
  on_off_stats: OnOffStats | null
  context: ImpactContext | null
  impact: ImpactRating | null
}

export interface ImpactLeaderboardEntry {
  id: number
  nba_id: number
  name: string
  position: string | null
  team_abbreviation: string | null
  contextualized_net_impact: number | null
  contextualized_off_impact: number | null
  contextualized_def_impact: number | null
  raw_net_rating_diff: number | null
  teammate_adjustment: number | null
  reliability_factor: number | null
  impact_percentile: number | null
}
