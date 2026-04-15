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
    age: data.age ? parseFloat(data.age) : 0,
    number: data.jersey_number ? parseInt(data.jersey_number, 10) || 0 : 0,
    heightInches: data.height_inches ?? null,
    college: data.college ?? null,
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
      lebron: n(aio?.lebron),
      darko: n(aio?.darko),
      laker: n(aio?.laker),
      mamba: n(aio?.mamba),
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
      handoff: mapPlayType(pt?.handoff),
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

    speedDistance: data.speed_distance
      ? {
          distMiles: n(data.speed_distance.dist_miles),
          distMilesOff: n(data.speed_distance.dist_miles_off),
          distMilesDef: n(data.speed_distance.dist_miles_def),
          avgSpeed: n(data.speed_distance.avg_speed),
          avgSpeedOff: n(data.speed_distance.avg_speed_off),
          avgSpeedDef: n(data.speed_distance.avg_speed_def),
        }
      : null,

    passing: data.passing
      ? {
          passesMade: n(data.passing.passes_made),
          passesReceived: n(data.passing.passes_received),
          secondaryAst: n(data.passing.secondary_ast),
          potentialAst: n(data.passing.potential_ast),
          astPointsCreated: n(data.passing.ast_points_created),
          astAdj: n(data.passing.ast_adj),
          astToPassPct: n(data.passing.ast_to_pass_pct),
          astToPassPctAdj: n(data.passing.ast_to_pass_pct_adj),
        }
      : null,

    reboundingTracking: data.rebounding_tracking
      ? {
          orebContestPct: n(data.rebounding_tracking.oreb_contest_pct),
          orebChancePct: n(data.rebounding_tracking.oreb_chance_pct),
          orebChancePctAdj: n(data.rebounding_tracking.oreb_chance_pct_adj),
          avgOrebDist: n(data.rebounding_tracking.avg_oreb_dist),
          drebContestPct: n(data.rebounding_tracking.dreb_contest_pct),
          drebChancePct: n(data.rebounding_tracking.dreb_chance_pct),
          drebChancePctAdj: n(data.rebounding_tracking.dreb_chance_pct_adj),
          avgDrebDist: n(data.rebounding_tracking.avg_dreb_dist),
          rebContestPct: n(data.rebounding_tracking.reb_contest_pct),
          rebChancePct: n(data.rebounding_tracking.reb_chance_pct),
          rebChancePctAdj: n(data.rebounding_tracking.reb_chance_pct_adj),
        }
      : null,

    recentGames: (data.recent_games ?? []).map((g) => ({
      gameDate: g.game_date ?? '',
      matchup: g.matchup ?? '',
      wl: g.wl ?? '',
      minutes: n(g.minutes),
      pts: g.pts ?? 0,
      reb: g.reb ?? 0,
      ast: g.ast ?? 0,
      stl: g.stl ?? 0,
      blk: g.blk ?? 0,
      tov: g.tov ?? 0,
      fgPct: n(g.fg_pct),
      fg3Pct: n(g.fg3_pct),
      plusMinus: g.plus_minus ?? 0,
      gameScore: n(g.game_score),
    })),

    consistency: data.consistency
      ? {
          gamesUsed: data.consistency.games_used ?? 0,
          ptsCv: n(data.consistency.pts_cv),
          astCv: n(data.consistency.ast_cv),
          rebCv: n(data.consistency.reb_cv),
          gameScoreCv: n(data.consistency.game_score_cv),
          gameScoreAvg: n(data.consistency.game_score_avg),
          gameScoreStd: n(data.consistency.game_score_std),
          gameScoreMax: n(data.consistency.game_score_max),
          gameScoreMin: n(data.consistency.game_score_min),
          boomGames: data.consistency.boom_games ?? 0,
          bustGames: data.consistency.bust_games ?? 0,
          boomPct: n(data.consistency.boom_pct),
          bustPct: n(data.consistency.bust_pct),
          bestStreak: data.consistency.best_streak ?? 0,
          worstStreak: data.consistency.worst_streak ?? 0,
          ddRate: n(data.consistency.dd_rate),
          tdRate: n(data.consistency.td_rate),
          consistencyScore: data.consistency.consistency_score ?? 0,
        }
      : null,

    defenderDistance: (data.defender_distance ?? []).map((d) => ({
      range: d.range,
      fgaFreq: n(d.fga_freq),
      fgPct: n(d.fg_pct),
      efgPct: n(d.efg_pct),
      fg3Pct: n(d.fg3_pct),
      fg2aFreq: n(d.fg2a_freq),
      fg2Pct: n(d.fg2_pct),
      fg3aFreq: n(d.fg3a_freq),
    })),

    touchesBreakdown: data.touches_breakdown
      ? {
          elbow: data.touches_breakdown.elbow
            ? { touches: n(data.touches_breakdown.elbow.touches), fga: n(data.touches_breakdown.elbow.fga), fgPct: n(data.touches_breakdown.elbow.fg_pct), fta: n(data.touches_breakdown.elbow.fta), pts: n(data.touches_breakdown.elbow.pts), passes: n(data.touches_breakdown.elbow.passes), ast: n(data.touches_breakdown.elbow.ast), tov: n(data.touches_breakdown.elbow.tov), fouls: n(data.touches_breakdown.elbow.fouls), ptsPerTouch: n(data.touches_breakdown.elbow.pts_per_touch) }
            : null,
          post: data.touches_breakdown.post
            ? { touches: n(data.touches_breakdown.post.touches), fga: n(data.touches_breakdown.post.fga), fgPct: n(data.touches_breakdown.post.fg_pct), fta: n(data.touches_breakdown.post.fta), pts: n(data.touches_breakdown.post.pts), passes: n(data.touches_breakdown.post.passes), ast: n(data.touches_breakdown.post.ast), tov: n(data.touches_breakdown.post.tov), fouls: n(data.touches_breakdown.post.fouls), ptsPerTouch: n(data.touches_breakdown.post.pts_per_touch) }
            : null,
          paint: data.touches_breakdown.paint
            ? { touches: n(data.touches_breakdown.paint.touches), fga: n(data.touches_breakdown.paint.fga), fgPct: n(data.touches_breakdown.paint.fg_pct), fta: n(data.touches_breakdown.paint.fta), pts: n(data.touches_breakdown.paint.pts), passes: n(data.touches_breakdown.paint.passes), ast: n(data.touches_breakdown.paint.ast), tov: n(data.touches_breakdown.paint.tov), fouls: n(data.touches_breakdown.paint.fouls), ptsPerTouch: n(data.touches_breakdown.paint.pts_per_touch) }
            : null,
        }
      : null,

    opponentShooting: data.opponent_shooting
      ? {
          games: data.opponent_shooting.games ?? 0,
          buckets: (data.opponent_shooting.buckets ?? []).map((b) => ({
            label: b.label,
            defendedFga: n(b.defended_fga),
            defendedFgPct: n(b.defended_fg_pct),
            normalFgPct: n(b.normal_fg_pct),
            pctPlusminus: n(b.pct_plusminus),
          })),
        }
      : null,

    defensivePlayTypes: data.defensive_play_types
      ? {
          isolation: data.defensive_play_types.isolation
            ? { poss: data.defensive_play_types.isolation.poss ?? 0, ppp: n(data.defensive_play_types.isolation.ppp), fgPct: n(data.defensive_play_types.isolation.fg_pct), tovPct: n(data.defensive_play_types.isolation.tov_pct), freq: n(data.defensive_play_types.isolation.freq), percentile: n(data.defensive_play_types.isolation.percentile) }
            : null,
          pnrBallHandler: data.defensive_play_types.pnr_ball_handler
            ? { poss: data.defensive_play_types.pnr_ball_handler.poss ?? 0, ppp: n(data.defensive_play_types.pnr_ball_handler.ppp), fgPct: n(data.defensive_play_types.pnr_ball_handler.fg_pct), tovPct: n(data.defensive_play_types.pnr_ball_handler.tov_pct), freq: n(data.defensive_play_types.pnr_ball_handler.freq), percentile: n(data.defensive_play_types.pnr_ball_handler.percentile) }
            : null,
          postUp: data.defensive_play_types.post_up
            ? { poss: data.defensive_play_types.post_up.poss ?? 0, ppp: n(data.defensive_play_types.post_up.ppp), fgPct: n(data.defensive_play_types.post_up.fg_pct), tovPct: n(data.defensive_play_types.post_up.tov_pct), freq: n(data.defensive_play_types.post_up.freq), percentile: n(data.defensive_play_types.post_up.percentile) }
            : null,
          spotUp: data.defensive_play_types.spot_up
            ? { poss: data.defensive_play_types.spot_up.poss ?? 0, ppp: n(data.defensive_play_types.spot_up.ppp), fgPct: n(data.defensive_play_types.spot_up.fg_pct), tovPct: n(data.defensive_play_types.spot_up.tov_pct), freq: n(data.defensive_play_types.spot_up.freq), percentile: n(data.defensive_play_types.spot_up.percentile) }
            : null,
          transition: data.defensive_play_types.transition
            ? { poss: data.defensive_play_types.transition.poss ?? 0, ppp: n(data.defensive_play_types.transition.ppp), fgPct: n(data.defensive_play_types.transition.fg_pct), tovPct: n(data.defensive_play_types.transition.tov_pct), freq: n(data.defensive_play_types.transition.freq), percentile: n(data.defensive_play_types.transition.percentile) }
            : null,
        }
      : null,
  }
}
