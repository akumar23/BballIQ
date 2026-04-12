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
 * tab components. Now includes real data for all-in-one metrics, portability,
 * championship, luck-adjusted, opponent tiers, matchup log, and scheme fits.
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
  const aio = data.all_in_one
  const luck = data.luck_adjusted
  const port = data.portability
  const champ = data.championship
  const defOv = def?.overview
  const lctx = data.lineup_context

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
      luck: {
        xWins: n(luck?.x_wins),
        actualWins: imp?.actual_wins ?? 0,
        clutchEPA: n(luck?.clutch_epa_per_game),
        garbageTimePts: n(luck?.garbage_time_ppg),
      },
      rapm: n(aio?.rapm),
      rpm: n(aio?.rpm),
      epm: n(aio?.epm),
      raptor: n(aio?.raptor),
      lebron: n(aio?.lebron),
      darko: n(aio?.darko),
      contextualized: {
        rawNetRtg: n(ctx?.raw_net_rtg),
        contextualizedNetRtg: n(ctx?.contextualized_net_rtg),
        percentile: ctx?.percentile ?? 0,
        adjustments: (ctx?.adjustments ?? []).map((a) => ({
          name: a.name,
          value: n(a.value),
          cumulative: n(a.cumulative),
          explanation: a.explanation,
        })),
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
        dRapm: n(aio?.rapm_defense),
        contestRate: n(defOv?.contest_rate),
        dfgPctDiff: n(def?.overall?.pct_plusminus),
        stlRate: n(defOv?.stl_rate),
        blkRate: n(defOv?.blk_rate),
        deflections: n(defOv?.deflections_per_game),
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
        contestsPerGame: n(defOv?.rim_contests_per_game),
        dfgPctAtRim: n(def?.rim?.d_fg_pct),
        diffVsLeague: n(def?.rim?.pct_plusminus),
      },
      matchupLog: data.matchup_log.map((m) => ({
        opponent: m.opponent,
        possessions: n(m.possessions),
        dfgPct: n(m.dfg_pct),
        ptsAllowed: n(m.pts_allowed),
      })),
    },

    timeline: data.career.map((s) => ({
      season: s.season,
      per: n(s.per),
      ws48: n(s.ws48),
      bpm: n(s.bpm),
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

    portability: {
      index: n(port?.index),
      grade: port?.grade ?? 'N/A',
      description: port ? `Portability grade: ${port.grade}` : 'Portability analysis not yet available.',
      subScores: {
        selfCreation: n(port?.self_creation),
        schemeFlexibility: n(port?.scheme_flexibility),
        defensiveSwitchability: n(port?.switchability),
        lowDependency: n(port?.low_dependency),
      },
      selfCreation: {
        unassistedPct: n(port?.unassisted_rate_score),
        assistedPct: 100 - n(port?.unassisted_rate_score),
        selfCreatedPpp: n(port?.self_created_ppp_score),
        gravityIndex: n(port?.gravity_score),
        analysis: '',
      },
      schemeCompatibility: (port?.scheme_scores ?? data.scheme_compatibility ?? []).map((s) => ({
        scheme: s.scheme,
        fitScore: n(s.fit_score),
        note: '',
      })),
      teammateDependency: {
        eliteSpacingTS: 0,
        poorSpacingTS: 0,
        spacingDelta: 0,
        withRimProtectorFg: 0,
        withoutRimProtectorFg: 0,
        dependencyScore: n(port?.low_dependency),
      },
      defensiveSwitchability: {
        guardablePositions: port?.positions_guarded
          ? Object.entries(port.positions_guarded)
              .filter(([, v]) => n(v) >= 50)
              .map(([k]) => k)
          : [],
        switchScore: n(port?.switchability),
        perimeterDfgDiff: n(def?.overall?.pct_plusminus),
        pnrNavigation: 0,
        scoutingNote: '',
      },
      projectedFits: [],
      historicalComps: [],
    },

    championship: {
      index: n(champ?.index),
      tier: champ?.tier ?? 'N/A',
      verdict: champ ? `${champ.tier} — Championship Index: ${n(champ.index).toFixed(1)}` : 'Championship index not yet available.',
      winProbability: n(champ?.win_probability) * 100,
      historicalBaseRate: 3.3,
      multiplier: n(champ?.multiplier_vs_base),
      pillars: (champ?.pillars ?? []).map((p) => ({
        name: p.name,
        score: n(p.score),
        weight: n(p.weight),
        explanation: '',
      })),
      playoffProjection: {
        ppg: n(champ?.playoff_projection?.projected_ppg),
        ts: n(champ?.playoff_projection?.projected_ts),
        ast: 0,
        drtg: 0,
        regToPlayoffDrop: {
          ppg: n(champ?.playoff_projection?.reg_ppg) - n(champ?.playoff_projection?.projected_ppg),
          ts: n(champ?.playoff_projection?.reg_ts) - n(champ?.playoff_projection?.projected_ts),
          ast: 0,
          drtg: 0,
        },
        comparisonNote: '',
      },
      supportingCast: { min2ndOption: '', spacingNeed: '', defensiveNeed: '', capFlexibility: '', blueprint: '' },
      comparables: [],
    },

    opponentTier: data.opponent_tiers.map((t) => ({
      tier: t.tier,
      netRtg: n(t.ppp_allowed),
      minutes: t.possessions ?? 0,
      weight: n(t.weight),
    })),

    lineupContext: {
      topLineups: (lctx?.top_lineups ?? []).map((l) => ({
        players: l.players,
        minutes: n(l.minutes),
        rawNet: n(l.raw_net),
        ctxNet: n(l.ctx_net),
        oppTier: l.opp_tier,
      })),
      withoutTopTeammate: {
        teammate: lctx?.without_top_teammate?.teammate ?? '',
        netRtg: n(lctx?.without_top_teammate?.net_rtg),
        minutes: n(lctx?.without_top_teammate?.minutes),
      },
    },
  }
}
