import type { CortexPlayer } from '../cortexTypes'

export const flagg: CortexPlayer = {
  id: 'flagg', name: 'Cooper Flagg', team: 'Duke (Projected)', position: 'PF', age: 18, number: 2, mpg: 28.0,
  traditional: { ppg: 18.4, rpg: 8.2, apg: 3.4, spg: 1.4, bpg: 2.2, fgPct: 0.458, threePct: 0.312, ftPct: 0.768, tov: 2.8 },
  advanced: { per: 24.2, ts: 0.548, ws48: 0.142, bpm: 5.8, vorp: 2.8, ortg: 108, drtg: 98, usg: 26.8, ows: 2.4, dws: 3.2 },
  impact: {
    onOff: { onORtg: 108, offORtg: 98, onDRtg: 98, offDRtg: 108, netSwing: 20.0 },
    luck: { xWins: 28, actualWins: 30, clutchEPA: 0.8, garbageTimePts: 1.2 },
    rapm: 3.2, rpm: 3.4, epm: 3.8, raptor: 3.2, lebron: 4.0, darko: 2.8,
    contextualized: {
      rawNetRtg: 10.0, contextualizedNetRtg: 5.4, percentile: 68,
      adjustments: [
        { name: 'Raw On/Off Net Rtg', value: 10.0, cumulative: 10.0, explanation: 'Strong college on/off — Duke is significantly better with him' },
        { name: 'Teammate Quality Adj', value: -1.2, cumulative: 8.8, explanation: 'Duke has solid college talent around him' },
        { name: 'Opponent Starter Adj', value: -0.8, cumulative: 8.0, explanation: 'College competition level — adjusted for strength of schedule' },
        { name: 'Garbage Time Filter', value: -1.4, cumulative: 6.6, explanation: 'College blowouts are more common — significant filter' },
        { name: 'Score Leverage Adj', value: -0.2, cumulative: 6.4, explanation: 'Limited clutch sample in college' },
        { name: 'Pace & Possession Adj', value: -1.0, cumulative: 5.4, explanation: 'College pace is faster — normalization reduces raw numbers' },
      ],
    },
  },
  playtype: {
    iso: { freq: 8.4, ppp: 0.82, rank: 0, efg: 0.38 },
    pnr_ball: { freq: 4.2, ppp: 0.78, rank: 0, efg: 0.36 },
    spot_up: { freq: 12.8, ppp: 0.92, rank: 0, efg: 0.44 },
    transition: { freq: 22.4, ppp: 1.18, rank: 0, efg: 0.58 },
    post_up: { freq: 14.8, ppp: 0.88, rank: 0, efg: 0.42 },
    cut: { freq: 16.2, ppp: 1.28, rank: 0, efg: 0.64 },
    off_screen: { freq: 8.8, ppp: 0.84, rank: 0, efg: 0.40 },
    handoff: { freq: 3.4, ppp: 0.78, rank: 0, efg: 0.36 },
  },
  shotZones: [
    { zone: 'Rim', fga: 6.8, fgPct: 0.592, freq: 34.2, leagueAvg: 0.628 },
    { zone: 'Short Mid', fga: 2.4, fgPct: 0.382, freq: 12.1, leagueAvg: 0.422 },
    { zone: 'Long Mid', fga: 2.8, fgPct: 0.352, freq: 14.1, leagueAvg: 0.408 },
    { zone: 'Corner 3', fga: 1.0, fgPct: 0.322, freq: 5.0, leagueAvg: 0.381 },
    { zone: 'Above Break 3', fga: 3.8, fgPct: 0.308, freq: 19.1, leagueAvg: 0.358 },
    { zone: 'FT', fga: 3.1, fgPct: 0.768, freq: 15.5, leagueAvg: 0.782 },
  ],
  defensive: {
    overview: { dRapm: 3.4, contestRate: 72.8, dfgPctDiff: -6.8, stlRate: 1.6, blkRate: 3.2, deflections: 3.4, rank: 0 },
    perimeter: {
      onBallDfg: 36.8, pullUpDfg: 35.2, catchShootDfg: 34.4,
      onBallDfgDiff: -6.6, pullUpDfgDiff: -6.4, catchShootDfgDiff: -3.3,
      tightContestRate: 72.4, screenNavRate: 68.2, avgContestDist: 3.2, dribblePctAllowed: 28.4,
      scoutingReport: 'Projectable defensive talent with elite instincts and length. Moves well laterally for his size. Active hands and shot-blocking ability are NBA-ready. Needs to add strength for NBA physicality.',
    },
    isolation: {
      isoDfg: 38.2, isoPpp: 0.82, isoRank: 0, possessions: 62,
      tovForcedPct: 12.4, freqTargeted: 6.4,
      byZone: [
        { zone: 'At Rim', dfgPct: 42.4, freq: 35 },
        { zone: 'Mid-Range', dfgPct: 36.8, freq: 40 },
        { zone: 'Three', dfgPct: 34.2, freq: 25 },
      ],
      scoutingReport: 'Impressive iso defense for a freshman. Length and instincts translate. Will improve as he adds NBA strength.',
    },
    rimProtection: { contestsPerGame: 4.8, dfgPctAtRim: 48.8, diffVsLeague: -14.0 },
    matchupLog: [
      { opponent: 'Hunter Dickinson', possessions: 28, dfgPct: 38.2, ptsAllowed: 12 },
      { opponent: 'Ryan Kalkbrenner', possessions: 24, dfgPct: 42.4, ptsAllowed: 14 },
      { opponent: 'Johni Broome', possessions: 26, dfgPct: 36.8, ptsAllowed: 10 },
    ],
  },
  timeline: [
    { season: '2024-25', per: 24.2, ws48: 0.142, bpm: 5.8, epm: 3.8 },
  ],
  radarData: [
    { stat: 'Scoring', value: 42 }, { stat: 'Playmaking', value: 48 },
    { stat: 'Defense', value: 82 }, { stat: 'Efficiency', value: 38 },
    { stat: 'Volume', value: 52 }, { stat: 'Durability', value: 58 },
    { stat: 'Clutch', value: 35 }, { stat: 'Versatility', value: 72 },
  ],
  portability: {
    index: 72, grade: 'B', description: 'Defensive foundation translates to any team. Offensive game needs significant development before portability as a scorer can be evaluated.',
    subScores: { selfCreation: 28, schemeFlexibility: 62, defensiveSwitchability: 82, lowDependency: 55 },
    selfCreation: { unassistedPct: 32, assistedPct: 68, selfCreatedPpp: 0.72, gravityIndex: 4.2, analysis: 'Limited self-creation — most scoring comes from transition, cuts, and putbacks. Handle and pull-up game need years of development.' },
    schemeCompatibility: [
      { scheme: 'Motion/Read', fitScore: 78, note: 'Good cutter and passer for size — will fit motion schemes' },
      { scheme: 'PnR Heavy', fitScore: 58, note: 'Not a PnR ball-handler yet — decent roll man potential' },
      { scheme: 'Iso-Heavy', fitScore: 35, note: 'Cannot isolate at NBA level — years away' },
      { scheme: 'Egalitarian', fitScore: 72, note: 'Versatile enough for balanced attack' },
      { scheme: 'Post-Up', fitScore: 62, note: 'Developing post game — needs strength' },
    ],
    teammateDependency: { eliteSpacingTS: 0.568, poorSpacingTS: 0.518, spacingDelta: 5.0, withRimProtectorFg: 0.458, withoutRimProtectorFg: 0.458, dependencyScore: 38 },
    defensiveSwitchability: { guardablePositions: ['SF', 'PF', 'C'], switchScore: 82, perimeterDfgDiff: -6.6, pnrNavigation: 68, scoutingNote: 'Can guard 3-5 with projection to guard 2-5 as he develops. Needs to improve lateral speed for guard matchups.' },
    projectedFits: [
      { team: 'OKC Thunder', archetype: 'Motion/Read', projectedNetRtg: 4.2, deltaFromCurrent: -1.2, fitScore: 88, reasoning: 'Defensive scheme maximizes his tools — SGA handles creation' },
      { team: 'Cleveland Cavaliers', archetype: 'PnR Heavy', projectedNetRtg: 3.8, deltaFromCurrent: -1.6, fitScore: 82, reasoning: 'Mitchell/Garland handle creation — Flagg provides defense' },
      { team: 'San Antonio Spurs', archetype: 'Motion/Read', projectedNetRtg: 3.2, deltaFromCurrent: -2.2, fitScore: 78, reasoning: 'Development situation with Wemby as defensive partner' },
      { team: 'Detroit Pistons', archetype: 'Egalitarian', projectedNetRtg: 2.4, deltaFromCurrent: -3.0, fitScore: 72, reasoning: 'Cade handles creation — Flagg adds defense and rebounding' },
    ],
    historicalComps: [
      { player: 'Scottie Barnes (2022)', similarity: 72, portabilityScore: 68, analysis: 'Versatile defensive forward with developing offense — Barnes showed the growth path' },
      { player: 'Jaren Jackson Jr. (2019)', similarity: 68, portabilityScore: 65, analysis: 'Shot-blocking forward with range potential — offense took time to develop' },
    ],
  },
  championship: {
    index: 32, tier: 'RAW PROSPECT',
    verdict: 'Defensive foundation is elite for a prospect but offense is years away from championship alpha level. Ceiling is a two-way franchise player (Giannis/Wemby tier) but floor is a high-level role player (Draymond/Scottie Barnes). Too early to project championship viability as a #1.',
    winProbability: 1.8, historicalBaseRate: 3.3, multiplier: 0.5,
    pillars: [
      { name: 'Playoff Scoring Projection', score: 22, weight: 25, explanation: 'Cannot score at NBA level yet — college numbers won\'t translate immediately' },
      { name: 'Two-Way Impact', score: 62, weight: 20, explanation: 'Defense is NBA-ready but offense is a project — one-sided currently' },
      { name: 'Clutch & Pressure', score: 25, weight: 15, explanation: 'No meaningful pressure experience — college doesn\'t compare' },
      { name: 'Portability / Roster Flexibility', score: 72, weight: 15, explanation: 'Defensive versatility translates — but can\'t evaluate offensive portability yet' },
      { name: 'Durability & Availability', score: 58, weight: 10, explanation: 'Young body — durability is unknown. Frame needs to fill out.' },
      { name: 'Playoff Experience & Growth Arc', score: 18, weight: 10, explanation: 'Zero professional experience — maximum growth runway' },
      { name: 'Supporting Cast Threshold', score: 12, weight: 5, explanation: 'Wherever he\'s drafted will be rebuilding' },
    ],
    playoffProjection: {
      ppg: 12.4, ts: 0.508, ast: 2.2, drtg: 102,
      regToPlayoffDrop: { ppg: -6.0, ts: -0.040, ast: -1.2, drtg: 4.0 },
      comparisonNote: 'Rookies historically struggle in playoffs. Wemby averaged 18/10/3 as a sophomore — that\'s the aspirational target.',
    },
    supportingCast: {
      min2ndOption: 'N/A — Flagg needs to be the #2-4 option initially', spacingNeed: 'High — limited shooting needs floor spacers around him',
      defensiveNeed: 'Moderate — provides defense himself but needs help', capFlexibility: 'Strong — rookie contract is max value',
      blueprint: 'Patient development on a team with a star creator. Think Scottie Barnes alongside Pascal Siakam/Fred VanVleet initially.',
    },
    comparables: [
      { player: 'Scottie Barnes', year: '2022', role: 'Rookie', castStrength: 72, championshipIndex: 28, won: false, analysis: 'Versatile defensive forward who needed time — Barnes is the realistic comp' },
      { player: 'Anthony Davis', year: '2013', role: 'Rookie', castStrength: 28, championshipIndex: 25, won: false, analysis: 'Ceiling comp — AD became a champion but took 8 years and LeBron' },
      { player: 'Andrew Wiggins', year: '2015', role: 'Rookie', castStrength: 32, championshipIndex: 22, won: false, analysis: 'Floor comp — athletic wing who never developed offensive game to alpha level' },
      { player: 'Kawhi Leonard', year: '2012', role: 'Rookie', castStrength: 88, championshipIndex: 18, won: true, analysis: 'Won as a role player initially — developed into alpha over 7 years. Aspirational trajectory.' },
    ],
  },
  opponentTier: [
    { tier: 'Elite Starters', netRtg: 1.8, minutes: 182, weight: 1.0 },
    { tier: 'Quality Starters', netRtg: 5.4, minutes: 328, weight: 0.8 },
    { tier: 'Role Players', netRtg: 10.2, minutes: 282, weight: 0.6 },
    { tier: 'Bench/Deep', netRtg: 16.8, minutes: 148, weight: 0.4 },
  ],
  lineupContext: {
    topLineups: [
      { players: ['Caleb Foster', 'Tyrese Proctor', 'Flagg', 'Mark Mitchell', 'Kyle Filipowski'], minutes: 248, rawNet: 12.8, ctxNet: 6.4, oppTier: 'Mixed' },
      { players: ['Foster', 'Proctor', 'Flagg', 'Mitchell', 'Dereck Lively'], minutes: 142, rawNet: 8.4, ctxNet: 4.2, oppTier: 'Quality' },
      { players: ['Jared McCain', 'Proctor', 'Flagg', 'Mitchell', 'Filipowski'], minutes: 108, rawNet: 6.2, ctxNet: 3.4, oppTier: 'Mixed' },
    ],
    withoutTopTeammate: { teammate: 'Tyrese Proctor', netRtg: 4.8, minutes: 178 },
  },
}
