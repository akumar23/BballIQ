import type { CortexPlayer } from '../cortexTypes'

export const wemby: CortexPlayer = {
  id: 'wemby', name: 'Victor Wembanyama', team: 'SAS Spurs', position: 'C', age: 21, number: 1, mpg: 31.5,
  traditional: { ppg: 24.8, rpg: 10.8, apg: 3.8, spg: 1.2, bpg: 3.8, fgPct: 0.478, threePct: 0.358, ftPct: 0.798, tov: 2.2 },
  advanced: { per: 26.8, ts: 0.588, ws48: 0.208, bpm: 7.2, vorp: 5.8, ortg: 118, drtg: 102, usg: 28.4, ows: 6.2, dws: 5.8 },
  impact: {
    onOff: { onORtg: 118, offORtg: 104, onDRtg: 102, offDRtg: 114, netSwing: 26.0 },
    luck: { xWins: 42, actualWins: 40, clutchEPA: 1.8, garbageTimePts: 1.4 },
    rapm: 5.8, rpm: 6.2, epm: 6.8, raptor: 6.4, lebron: 7.1, darko: 5.2,
    contextualized: {
      rawNetRtg: 16.0, contextualizedNetRtg: 10.8, percentile: 95,
      adjustments: [
        { name: 'Raw On/Off Net Rtg', value: 16.0, cumulative: 16.0, explanation: 'Massive swing — Spurs are a different team without him' },
        { name: 'Teammate Quality Adj', value: 2.8, cumulative: 18.8, explanation: 'Spurs roster is below-average — inflates his on/off' },
        { name: 'Opponent Starter Adj', value: -0.4, cumulative: 18.4, explanation: 'Rests more vs starters in blowout losses' },
        { name: 'Garbage Time Filter', value: -4.2, cumulative: 14.2, explanation: 'Significant garbage time in both directions (Spurs lose big too)' },
        { name: 'Score Leverage Adj', value: -1.8, cumulative: 12.4, explanation: 'Less high-leverage experience on a rebuilding team' },
        { name: 'Pace & Possession Adj', value: -1.6, cumulative: 10.8, explanation: 'Spurs play fast — pace normalization reduces raw impact' },
      ],
    },
  },
  playtype: {
    iso: { freq: 8.2, ppp: 0.92, rank: 48, efg: 0.42 },
    pnr_ball: { freq: 6.8, ppp: 0.88, rank: 72, efg: 0.40 },
    spot_up: { freq: 14.2, ppp: 1.08, rank: 18, efg: 0.52 },
    transition: { freq: 16.8, ppp: 1.22, rank: 8, efg: 0.60 },
    post_up: { freq: 18.4, ppp: 1.02, rank: 8, efg: 0.48 },
    cut: { freq: 12.8, ppp: 1.42, rank: 4, efg: 0.74 },
    off_screen: { freq: 8.2, ppp: 0.96, rank: 38, efg: 0.44 },
    handoff: { freq: 5.6, ppp: 0.94, rank: 52, efg: 0.42 },
  },
  shotZones: [
    { zone: 'Rim', fga: 7.2, fgPct: 0.648, freq: 30.2, leagueAvg: 0.628 },
    { zone: 'Short Mid', fga: 2.8, fgPct: 0.412, freq: 11.8, leagueAvg: 0.422 },
    { zone: 'Long Mid', fga: 3.2, fgPct: 0.388, freq: 13.4, leagueAvg: 0.408 },
    { zone: 'Corner 3', fga: 1.4, fgPct: 0.378, freq: 5.9, leagueAvg: 0.381 },
    { zone: 'Above Break 3', fga: 5.8, fgPct: 0.352, freq: 24.4, leagueAvg: 0.358 },
    { zone: 'FT', fga: 3.4, fgPct: 0.798, freq: 14.3, leagueAvg: 0.782 },
  ],
  defensive: {
    overview: { dRapm: 4.8, contestRate: 78.4, dfgPctDiff: -8.2, stlRate: 1.4, blkRate: 5.2, deflections: 4.2, rank: 1 },
    perimeter: {
      onBallDfg: 36.4, pullUpDfg: 34.8, catchShootDfg: 32.1,
      onBallDfgDiff: -7.0, pullUpDfgDiff: -6.8, catchShootDfgDiff: -5.6,
      tightContestRate: 78.2, screenNavRate: 72.8, avgContestDist: 2.8, dribblePctAllowed: 22.4,
      scoutingReport: 'Generational shot-blocker who alters every shot in his airspace. 7\'4 wingspan covers ground no other player can. Improving perimeter switchability each month.',
    },
    isolation: {
      isoDfg: 34.2, isoPpp: 0.72, isoRank: 2, possessions: 118,
      tovForcedPct: 16.8, freqTargeted: 5.8,
      byZone: [
        { zone: 'At Rim', dfgPct: 38.2, freq: 32 },
        { zone: 'Mid-Range', dfgPct: 32.8, freq: 42 },
        { zone: 'Three', dfgPct: 30.4, freq: 26 },
      ],
      scoutingReport: 'Opponents avoid isolating against him. When forced, he uses length to contest everything without fouling.',
    },
    rimProtection: { contestsPerGame: 6.8, dfgPctAtRim: 48.2, diffVsLeague: -14.6 },
    matchupLog: [
      { opponent: 'Nikola Jokic', possessions: 45, dfgPct: 42.1, ptsAllowed: 24 },
      { opponent: 'Anthony Davis', possessions: 42, dfgPct: 38.8, ptsAllowed: 18 },
      { opponent: 'Joel Embiid', possessions: 38, dfgPct: 44.2, ptsAllowed: 22 },
    ],
  },
  timeline: [
    { season: '2023-24', per: 22.4, ws48: 0.168, bpm: 4.8, epm: 4.2 },
    { season: '2024-25', per: 26.8, ws48: 0.208, bpm: 7.2, epm: 6.8 },
  ],
  radarData: [
    { stat: 'Scoring', value: 72 }, { stat: 'Playmaking', value: 55 },
    { stat: 'Defense', value: 98 }, { stat: 'Efficiency', value: 68 },
    { stat: 'Volume', value: 78 }, { stat: 'Durability', value: 65 },
    { stat: 'Clutch', value: 58 }, { stat: 'Versatility', value: 92 },
  ],
  portability: {
    index: 85, grade: 'A', description: 'Defensive anchor who fits any system. Offensive limitations are the only portability concern — will improve as shot creation develops.',
    subScores: { selfCreation: 58, schemeFlexibility: 82, defensiveSwitchability: 96, lowDependency: 78 },
    selfCreation: { unassistedPct: 38, assistedPct: 62, selfCreatedPpp: 0.88, gravityIndex: 7.8, analysis: 'Rim protection gravity is immense but offensive self-creation is still developing. Post moves and face-up game improving rapidly.' },
    schemeCompatibility: [
      { scheme: 'Motion/Read', fitScore: 88, note: 'Good passer for size — fits motion concepts well' },
      { scheme: 'PnR Heavy', fitScore: 82, note: 'Elite roll threat and lob target' },
      { scheme: 'Iso-Heavy', fitScore: 58, note: 'Not yet an isolation scorer — developing' },
      { scheme: 'Egalitarian', fitScore: 90, note: 'Versatile enough to play any role' },
      { scheme: 'Post-Up', fitScore: 78, note: 'Post game improving but not yet dominant' },
    ],
    teammateDependency: { eliteSpacingTS: 0.608, poorSpacingTS: 0.558, spacingDelta: 5.0, withRimProtectorFg: 0.478, withoutRimProtectorFg: 0.478, dependencyScore: 28 },
    defensiveSwitchability: { guardablePositions: ['PG', 'SG', 'SF', 'PF', 'C'], switchScore: 96, perimeterDfgDiff: -7.0, pnrNavigation: 72, scoutingNote: 'Can guard all 5 positions. Length makes him a unicorn defender — covers ground and contests shots at every level.' },
    projectedFits: [
      { team: 'OKC Thunder', archetype: 'Motion/Read', projectedNetRtg: 12.4, deltaFromCurrent: 1.6, fitScore: 98, reasoning: 'Defensive scheme + SGA creation = ideal pairing' },
      { team: 'Boston Celtics', archetype: 'Egalitarian', projectedNetRtg: 11.8, deltaFromCurrent: 1.0, fitScore: 95, reasoning: 'Replaces any center and adds DPOY-level defense' },
      { team: 'Dallas Mavericks', archetype: 'PnR Heavy', projectedNetRtg: 10.2, deltaFromCurrent: -0.6, fitScore: 92, reasoning: 'Luka-Wemby PnR would be historic, but spacing concerns' },
      { team: 'New York Knicks', archetype: 'Iso-Heavy', projectedNetRtg: 9.4, deltaFromCurrent: -1.4, fitScore: 85, reasoning: 'Defensive anchor for Brunson — less offensive role but high impact' },
    ],
    historicalComps: [
      { player: 'Tim Duncan (2001)', similarity: 74, portabilityScore: 88, analysis: 'Two-way big who anchored any roster. Wemby has more perimeter versatility.' },
      { player: 'Kevin Garnett (2004)', similarity: 78, portabilityScore: 82, analysis: 'Defensive anchor with developing offense — similar trajectory arc' },
    ],
  },
  championship: {
    index: 68, tier: 'FUTURE ALPHA',
    verdict: 'Generational defensive talent with the highest ceiling in the NBA. Offense needs 2-3 more years of development to reach championship alpha level. Currently a championship piece, not yet the #1 option on a title team.',
    winProbability: 8.2, historicalBaseRate: 3.3, multiplier: 2.5,
    pillars: [
      { name: 'Playoff Scoring Projection', score: 58, weight: 25, explanation: 'Offensive creation still developing — playoff scoring will be challenged initially' },
      { name: 'Two-Way Impact', score: 92, weight: 20, explanation: 'Already DPOY-caliber — defense alone makes teams contenders' },
      { name: 'Clutch & Pressure', score: 52, weight: 15, explanation: 'Limited clutch sample — hasn\'t been in meaningful pressure situations yet' },
      { name: 'Portability / Roster Flexibility', score: 85, weight: 15, explanation: 'Fits any roster as a defensive anchor' },
      { name: 'Durability & Availability', score: 62, weight: 10, explanation: 'Frame concerns — has missed time with minor injuries' },
      { name: 'Playoff Experience & Growth Arc', score: 45, weight: 10, explanation: 'Zero playoff experience — steep growth curve ahead' },
      { name: 'Supporting Cast Threshold', score: 42, weight: 5, explanation: 'Spurs roster is rebuilding — years away from contention' },
    ],
    playoffProjection: {
      ppg: 22.4, ts: 0.558, ast: 3.4, drtg: 104,
      regToPlayoffDrop: { ppg: -2.4, ts: -0.030, ast: -0.4, drtg: 2.0 },
      comparisonNote: 'Young bigs typically see playoff efficiency dips. Duncan averaged 23/11/3 in his first playoffs at age 22.',
    },
    supportingCast: {
      min2ndOption: 'All-Star perimeter creator', spacingNeed: 'High — needs shooters around him',
      defensiveNeed: 'Moderate — he IS the defensive anchor', capFlexibility: 'Strong — Spurs have max space',
      blueprint: 'Elite perimeter scorer (#1A) + 3&D wings + secondary playmaker. Spurs need a Brunson/SGA-tier guard.',
    },
    comparables: [
      { player: 'Tim Duncan', year: '1999', role: '#1 Option', castStrength: 72, championshipIndex: 82, won: true, analysis: 'Won title in year 2 with elite defense and good-not-great offense — Wemby has similar trajectory' },
      { player: 'Anthony Davis', year: '2020', role: '#2 Option', castStrength: 92, championshipIndex: 72, won: true, analysis: 'Defensive big who needed elite #1 (LeBron) to win — ceiling comp if offense doesn\'t develop' },
      { player: 'Kevin Garnett', year: '2004', role: '#1 Option', castStrength: 48, championshipIndex: 75, won: false, analysis: 'DPOY-caliber big who couldn\'t win alone — needed Boston trade for ring' },
      { player: 'Hakeem Olajuwon', year: '1986', role: '#1 Option', castStrength: 62, championshipIndex: 68, won: false, analysis: 'Young Hakeem with elite defense — took 8 more years to win title' },
    ],
  },
  opponentTier: [
    { tier: 'Elite Starters', netRtg: 4.2, minutes: 362, weight: 1.0 },
    { tier: 'Quality Starters', netRtg: 8.8, minutes: 598, weight: 0.8 },
    { tier: 'Role Players', netRtg: 14.8, minutes: 488, weight: 0.6 },
    { tier: 'Bench/Deep', netRtg: 21.2, minutes: 268, weight: 0.4 },
  ],
  lineupContext: {
    topLineups: [
      { players: ['Tre Jones', 'Devin Vassell', 'Keldon Johnson', 'Jeremy Sochan', 'Wembanyama'], minutes: 388, rawNet: 12.4, ctxNet: 8.2, oppTier: 'Mixed' },
      { players: ['Chris Paul', 'Vassell', 'Johnson', 'Sochan', 'Wembanyama'], minutes: 212, rawNet: 14.8, ctxNet: 9.8, oppTier: 'Quality' },
      { players: ['Tre Jones', 'Vassell', 'Malaki Branham', 'Sochan', 'Wembanyama'], minutes: 168, rawNet: 6.8, ctxNet: 4.2, oppTier: 'Mixed' },
    ],
    withoutTopTeammate: { teammate: 'Devin Vassell', netRtg: 6.2, minutes: 318 },
  },
}
