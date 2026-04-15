export interface CortexPlayer {
  id: string
  name: string
  team: string
  position: string
  age: number
  number: number
  heightInches?: number | null
  college?: string | null
  mpg: number
  traditional: { ppg: number; rpg: number; apg: number; spg: number; bpg: number; fgPct: number; threePct: number; ftPct: number; tov: number }
  advanced: { per: number; ts: number; ws48: number; bpm: number; vorp: number; ortg: number; drtg: number; usg: number; ows: number; dws: number }
  impact: {
    onOff: { onORtg: number; offORtg: number; onDRtg: number; offDRtg: number; netSwing: number }
    luck: { xWins: number; actualWins: number; clutchEPA: number; garbageTimePts: number }
    rapm: number; rpm: number; epm: number; lebron: number; darko: number; laker: number; mamba: number
    contextualized: {
      rawNetRtg: number; contextualizedNetRtg: number; percentile: number
      adjustments: Array<{ name: string; value: number; cumulative: number; explanation: string }>
    }
  }
  playtype: Record<string, { freq: number; ppp: number; rank: number; efg: number }>
  shotZones: Array<{ zone: string; fga: number; fgPct: number; freq: number; leagueAvg: number }>
  defensive: {
    overview: { dRapm: number; contestRate: number; dfgPctDiff: number; stlRate: number; blkRate: number; deflections: number; rank: number }
    perimeter: { onBallDfg: number; pullUpDfg: number; catchShootDfg: number; onBallDfgDiff: number; pullUpDfgDiff: number; catchShootDfgDiff: number; tightContestRate: number; screenNavRate: number; avgContestDist: number; dribblePctAllowed: number; scoutingReport: string }
    isolation: { isoDfg: number; isoPpp: number; isoRank: number; possessions: number; tovForcedPct: number; freqTargeted: number; byZone: Array<{ zone: string; dfgPct: number; freq: number }>; scoutingReport: string }
    rimProtection: { contestsPerGame: number; dfgPctAtRim: number; diffVsLeague: number }
    matchupLog: Array<{ opponent: string; possessions: number; dfgPct: number; ptsAllowed: number }>
  }
  timeline: Array<{ season: string; per: number; ws48: number; bpm: number; epm: number }>
  radarData: Array<{ stat: string; value: number }>
  portability: {
    index: number; grade: string; description: string
    subScores: { selfCreation: number; schemeFlexibility: number; defensiveSwitchability: number; lowDependency: number }
    selfCreation: { unassistedPct: number; assistedPct: number; selfCreatedPpp: number; gravityIndex: number; analysis: string }
    schemeCompatibility: Array<{ scheme: string; fitScore: number; note: string }>
    teammateDependency: { eliteSpacingTS: number; poorSpacingTS: number; spacingDelta: number; withRimProtectorFg: number; withoutRimProtectorFg: number; dependencyScore: number }
    defensiveSwitchability: { guardablePositions: string[]; switchScore: number; perimeterDfgDiff: number; pnrNavigation: number; scoutingNote: string }
    projectedFits: Array<{ team: string; archetype: string; projectedNetRtg: number; deltaFromCurrent: number; fitScore: number; reasoning: string }>
    historicalComps: Array<{ player: string; similarity: number; portabilityScore: number; analysis: string }>
  }
  championship: {
    index: number; tier: string; verdict: string; winProbability: number; historicalBaseRate: number; multiplier: number
    pillars: Array<{ name: string; score: number; weight: number; explanation: string }>
    playoffProjection: { ppg: number; ts: number; ast: number; drtg: number; regToPlayoffDrop: { ppg: number; ts: number; ast: number; drtg: number }; comparisonNote: string }
    supportingCast: { min2ndOption: string; spacingNeed: string; defensiveNeed: string; capFlexibility: string; blueprint: string }
    comparables: Array<{ player: string; year: string; role: string; castStrength: number; championshipIndex: number; won: boolean; analysis: string }>
  }
  opponentTier: Array<{ tier: string; netRtg: number; minutes: number; weight: number }>
  lineupContext: {
    topLineups: Array<{ players: string[]; minutes: number; rawNet: number; ctxNet: number; oppTier: string }>
    withoutTopTeammate: { teammate: string; netRtg: number; minutes: number }
  }
  speedDistance?: { distMiles: number; distMilesOff: number; distMilesDef: number; avgSpeed: number; avgSpeedOff: number; avgSpeedDef: number } | null
  passing?: { passesMade: number; passesReceived: number; secondaryAst: number; potentialAst: number; astPointsCreated: number; astAdj: number; astToPassPct: number; astToPassPctAdj: number } | null
  reboundingTracking?: { orebContestPct: number; orebChancePct: number; orebChancePctAdj: number; avgOrebDist: number; drebContestPct: number; drebChancePct: number; drebChancePctAdj: number; avgDrebDist: number; rebContestPct: number; rebChancePct: number; rebChancePctAdj: number } | null
  defenderDistance?: Array<{ range: string; fgaFreq: number; fgPct: number; efgPct: number; fg3Pct: number; fg2aFreq: number; fg2Pct: number; fg3aFreq: number }>
  touchesBreakdown?: {
    elbow: { touches: number; fga: number; fgPct: number; fta: number; pts: number; passes: number; ast: number; tov: number; fouls: number; ptsPerTouch: number } | null
    post: { touches: number; fga: number; fgPct: number; fta: number; pts: number; passes: number; ast: number; tov: number; fouls: number; ptsPerTouch: number } | null
    paint: { touches: number; fga: number; fgPct: number; fta: number; pts: number; passes: number; ast: number; tov: number; fouls: number; ptsPerTouch: number } | null
  } | null
  opponentShooting?: {
    games: number
    buckets: Array<{ label: string; defendedFga: number; defendedFgPct: number; normalFgPct: number; pctPlusminus: number }>
  } | null
  recentGames?: Array<{ gameDate: string; matchup: string; wl: string; minutes: number; pts: number; reb: number; ast: number; stl: number; blk: number; tov: number; fgPct: number; fg3Pct: number; plusMinus: number; gameScore: number }>
  consistency?: {
    gamesUsed: number; ptsCv: number; astCv: number; rebCv: number; gameScoreCv: number
    gameScoreAvg: number; gameScoreStd: number; gameScoreMax: number; gameScoreMin: number
    boomGames: number; bustGames: number; boomPct: number; bustPct: number
    bestStreak: number; worstStreak: number; ddRate: number; tdRate: number
    consistencyScore: number
  } | null
  defensivePlayTypes?: {
    isolation: { poss: number; ppp: number; fgPct: number; tovPct: number; freq: number; percentile: number } | null
    pnrBallHandler: { poss: number; ppp: number; fgPct: number; tovPct: number; freq: number; percentile: number } | null
    postUp: { poss: number; ppp: number; fgPct: number; tovPct: number; freq: number; percentile: number } | null
    spotUp: { poss: number; ppp: number; fgPct: number; tovPct: number; freq: number; percentile: number } | null
    transition: { poss: number; ppp: number; fgPct: number; tovPct: number; freq: number; percentile: number } | null
  } | null
}
