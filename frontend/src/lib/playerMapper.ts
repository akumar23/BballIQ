import type { CortexPlayer } from '@/data/cortexTypes'
import type { ApiCardPlayType, PlayerCardData } from '@/types/playerCard'

/** Safely parse a Decimal string (or number) to a JS number, defaulting to 0. */
const n = (v: string | number | null | undefined): number => Number(v ?? 0)

function mapPlayType(pt: ApiCardPlayType | null | undefined): { freq: number; ppp: number; rank: number; efg: number } {
  if (!pt) return { freq: 0, ppp: 0, rank: 0, efg: 0 }
  return {
    freq: n(pt.frequency),
    ppp: n(pt.ppp),
    // Convert ppp_percentile (0-100) to an approximate rank out of 100
    rank: pt.ppp_percentile != null ? Math.max(1, 101 - pt.ppp_percentile) : 0,
    efg: n(pt.fg_pct),
  }
}

/**
 * Maps the API PlayerCardData response to the CortexPlayer shape used by all
 * tab components. Fields not available in the backend (EPM, RAPM, portability,
 * championship, etc.) are zeroed/empty so tabs render without crashing.
 */
export function mapApiToPlayer(data: PlayerCardData): CortexPlayer {
  const t = data.traditional
  const adv = data.advanced
  const imp = data.impact
  const oo = imp?.on_off
  const ctx = imp?.contextualized
  const pt = data.play_types
  const def = data.defensive
  const rad = data.radar

  return {
    id: String(data.id),
    name: data.name,
    team: data.team_abbreviation ?? 'N/A',
    position: data.position ?? 'N/A',
    age: 0,
    number: 0,
    mpg: n(t?.mpg),

    traditional: {
      ppg: n(t?.ppg),
      rpg: n(t?.rpg),
      apg: n(t?.apg),
      spg: n(t?.spg),
      bpg: n(t?.bpg),
      fgPct: n(t?.fg_pct),
      threePct: n(t?.fg3_pct),
      ftPct: n(t?.ft_pct),
      tov: n(t?.tov),
    },

    advanced: {
      per: n(adv?.per),
      ts: n(adv?.ts_pct),
      ws48: n(adv?.ws48),
      bpm: n(adv?.bpm),
      vorp: n(adv?.vorp),
      ortg: n(adv?.ortg),
      drtg: n(adv?.drtg),
      usg: n(adv?.usg_pct),
      ows: n(adv?.ows),
      dws: n(adv?.dws),
    },

    impact: {
      onOff: {
        onORtg: n(oo?.on_ortg),
        offORtg: n(oo?.off_ortg),
        onDRtg: n(oo?.on_drtg),
        offDRtg: n(oo?.off_drtg),
        netSwing: n(oo?.net_swing),
      },
      // Luck metrics not in DB — zeroed
      luck: { xWins: 0, actualWins: 0, clutchEPA: 0, garbageTimePts: 0 },
      // Proprietary third-party metrics not available — zeroed
      rapm: 0,
      rpm: 0,
      epm: 0,
      raptor: 0,
      lebron: 0,
      darko: 0,
      contextualized: {
        rawNetRtg: n(ctx?.raw_net_rtg),
        contextualizedNetRtg: n(ctx?.contextualized_net_rtg),
        percentile: ctx?.percentile ?? 0,
        // Step-by-step adjustment breakdown not stored in DB
        adjustments: [],
      },
    },

    playtype: {
      iso: mapPlayType(pt?.isolation),
      pnr_ball: mapPlayType(pt?.pnr_ball_handler),
      pnr_roll: mapPlayType(pt?.pnr_roll_man),
      post_up: mapPlayType(pt?.post_up),
      spot_up: mapPlayType(pt?.spot_up),
      transition: mapPlayType(pt?.transition),
      cut: mapPlayType(pt?.cut),
      off_screen: mapPlayType(pt?.off_screen),
      // Handoff not tracked in DB
      handoff: { freq: 0, ppp: 0, rank: 0, efg: 0 },
    },

    shotZones: data.shot_zones.map((z) => ({
      zone: z.zone,
      fga: n(z.fga_per_game),
      fgPct: n(z.fg_pct),
      freq: n(z.freq),
      leagueAvg: n(z.league_avg),
    })),

    defensive: {
      overview: {
        dRapm: 0, // not in DB
        contestRate: 0,
        dfgPctDiff: n(def?.overall?.pct_plusminus),
        stlRate: 0,
        blkRate: 0,
        deflections: 0,
        rank: 0,
      },
      perimeter: {
        onBallDfg: n(def?.overall?.d_fg_pct),
        pullUpDfg: 0,
        catchShootDfg: 0,
        onBallDfgDiff: n(def?.overall?.pct_plusminus),
        pullUpDfgDiff: 0,
        catchShootDfgDiff: 0,
        tightContestRate: 0,
        screenNavRate: 0,
        avgContestDist: 0,
        dribblePctAllowed: 0,
        scoutingReport: '',
      },
      isolation: {
        isoDfg: n(def?.iso_defense?.fg_pct),
        isoPpp: n(def?.iso_defense?.ppp),
        isoRank: def?.iso_defense?.percentile ?? 0,
        possessions: def?.iso_defense?.poss ?? 0,
        tovForcedPct: 0,
        freqTargeted: 0,
        byZone: [],
        scoutingReport: '',
      },
      rimProtection: {
        contestsPerGame: 0,
        dfgPctAtRim: n(def?.rim?.d_fg_pct),
        diffVsLeague: n(def?.rim?.pct_plusminus),
      },
      matchupLog: [],
    },

    // Career timeline — currently only has traditional stats per season.
    // per/ws48/bpm/epm require historical computed data not yet stored.
    timeline: data.career.map((s) => ({
      season: s.season,
      per: 0,
      ws48: 0,
      bpm: 0,
      epm: 0,
    })),

    radarData: rad
      ? [
          { stat: 'Scoring', value: rad.scoring ?? 0 },
          { stat: 'Playmaking', value: rad.playmaking ?? 0 },
          { stat: 'Defense', value: rad.defense ?? 0 },
          { stat: 'Efficiency', value: rad.efficiency ?? 0 },
          { stat: 'Volume', value: rad.volume ?? 0 },
          { stat: 'Durability', value: rad.durability ?? 0 },
          { stat: 'Clutch', value: rad.clutch ?? 0 },
          { stat: 'Versatility', value: rad.versatility ?? 0 },
        ]
      : [],

    // Portability, championship, lineup context not computed in backend
    portability: {
      index: 0,
      grade: 'N/A',
      description: 'Portability analysis not yet available.',
      subScores: { selfCreation: 0, schemeFlexibility: 0, defensiveSwitchability: 0, lowDependency: 0 },
      selfCreation: { unassistedPct: 0, assistedPct: 0, selfCreatedPpp: 0, gravityIndex: 0, analysis: '' },
      schemeCompatibility: [],
      teammateDependency: {
        eliteSpacingTS: 0,
        poorSpacingTS: 0,
        spacingDelta: 0,
        withRimProtectorFg: 0,
        withoutRimProtectorFg: 0,
        dependencyScore: 0,
      },
      defensiveSwitchability: {
        guardablePositions: [],
        switchScore: 0,
        perimeterDfgDiff: 0,
        pnrNavigation: 0,
        scoutingNote: '',
      },
      projectedFits: [],
      historicalComps: [],
    },

    championship: {
      index: 0,
      tier: 'N/A',
      verdict: 'Championship index not yet available.',
      winProbability: 0,
      historicalBaseRate: 3.3,
      multiplier: 0,
      pillars: [],
      playoffProjection: {
        ppg: 0,
        ts: 0,
        ast: 0,
        drtg: 0,
        regToPlayoffDrop: { ppg: 0, ts: 0, ast: 0, drtg: 0 },
        comparisonNote: '',
      },
      supportingCast: { min2ndOption: '', spacingNeed: '', defensiveNeed: '', capFlexibility: '', blueprint: '' },
      comparables: [],
    },

    opponentTier: [],
    lineupContext: {
      topLineups: [],
      withoutTopTeammate: { teammate: '', netRtg: 0, minutes: 0 },
    },
  }
}
