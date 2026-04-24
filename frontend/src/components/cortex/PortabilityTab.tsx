import type { CortexPlayer } from '@/data/cortexTypes'
import { SectionHeader, StatBox, fitColor } from './shared'

/** Format a signed Net Rating value with one decimal, or "N/A" when null. */
function formatNrtg(value: number | null): string {
  if (value === null) return 'N/A'
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}`
}

/** Color an NRtg value: positive = green, negative = red, near-zero = yellow. */
function nrtgColor(value: number | null): string {
  if (value === null) return 'text-gray-400'
  if (value >= 2) return 'text-green-600'
  if (value <= -2) return 'text-red-600'
  return 'text-yellow-600'
}

/** Render a sample-size hint beneath a bucket value. */
function formatMinutes(minutes: number): string {
  if (!minutes || minutes <= 0) return '0 min'
  return `${Math.round(minutes)} min`
}

/** Clamp a 0..1 ratio to a percentage for width styling. */
function pctWidth(value: number, ceiling: number): string {
  if (!Number.isFinite(value) || ceiling <= 0) return '0%'
  return `${Math.max(0, Math.min(100, (value / ceiling) * 100))}%`
}

/** Format a signed percent with one decimal (e.g. +3.2%, -1.4%). */
function formatSignedPct(value: number): string {
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

export default function PortabilityTab({ player }: { player: CortexPlayer }) {
  const p = player.portability
  const fe = player.frictionEfficiency
  const gi = player.gravityIndex
  const sd = player.shotDiet
  const rg = player.rimGravity
  const pf = player.passFunnel
  const lst = player.lateSeasonTrend
  const lb = player.lineupBuoyancy
  const sr = player.schemeRobustness
  const hasAdvancedSignals = Boolean(fe || gi || sd || rg || pf || lst || lb || sr)

  return (
    <div>
      {/* Portability Index */}
      <SectionHeader title="Portability Index" tag="TRANSFER ANALYSIS" />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 flex flex-col items-center justify-center">
          <svg width="140" height="140" viewBox="0 0 140 140">
            <circle cx="70" cy="70" r="58" fill="none" stroke="#e5e7eb" strokeWidth="8" />
            <circle cx="70" cy="70" r="58" fill="none" stroke="#2563eb" strokeWidth="8"
              strokeDasharray={`${(p.index / 100) * 364.4} 364.4`}
              strokeLinecap="round" transform="rotate(-90 70 70)" />
            <text x="70" y="62" textAnchor="middle" className="fill-gray-900 text-3xl font-mono font-bold">{p.index}</text>
            <text x="70" y="82" textAnchor="middle" className="fill-primary-600 text-sm font-mono">{p.grade}</text>
          </svg>
          <p className="text-sm text-gray-500 mt-3 text-center">{p.description}</p>
        </div>
        <div className="lg:col-span-2 grid grid-cols-2 gap-3">
          {[
            { label: 'Self-Creation', val: p.subScores.selfCreation },
            { label: 'Scheme Flexibility', val: p.subScores.schemeFlexibility },
            { label: 'Def. Switchability', val: p.subScores.defensiveSwitchability },
            { label: 'Low Dependency', val: p.subScores.lowDependency },
          ].map((s) => (
            <div key={s.label} className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider">{s.label}</p>
              <p className="text-2xl font-mono font-bold text-gray-900 mt-1">{s.val}</p>
              <div className="w-full bg-gray-100 rounded-full h-1.5 mt-2">
                <div className={`h-1.5 rounded-full ${fitColor(s.val)}`} style={{ width: `${s.val}%` }} />
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Self-Creation Profile */}
      <SectionHeader title="Self-Creation Profile" />
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4">
        <div className="flex items-center gap-2 mb-3">
          <div className="flex-1 bg-primary-600/20 rounded-l-full h-6 relative" style={{ width: `${p.selfCreation.unassistedPct}%` }}>
            <span className="absolute inset-0 flex items-center justify-center text-[10px] font-mono text-primary-700">{p.selfCreation.unassistedPct}% Unassisted</span>
          </div>
          <div className="flex-1 bg-gray-100 rounded-r-full h-6 relative" style={{ width: `${p.selfCreation.assistedPct}%` }}>
            <span className="absolute inset-0 flex items-center justify-center text-[10px] font-mono text-gray-500">{p.selfCreation.assistedPct}% Assisted</span>
          </div>
        </div>
        <div className="grid grid-cols-2 gap-3 mb-3">
          <StatBox label="Self-Created PPP" value={p.selfCreation.selfCreatedPpp.toFixed(2)} />
          <StatBox label="Gravity Index" value={p.selfCreation.gravityIndex.toFixed(1)} />
        </div>
        <p className="text-sm text-gray-500">{p.selfCreation.analysis}</p>
      </div>

      {/* Scheme Compatibility */}
      <SectionHeader title="Scheme Compatibility" />
      <div className="space-y-2 mb-4">
        {p.schemeCompatibility.map((s) => (
          <div key={s.scheme} className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className="flex items-center gap-4">
              <div className="w-32 shrink-0">
                <p className="text-sm text-gray-900">{s.scheme}</p>
              </div>
              <div className="w-12 shrink-0 text-right">
                <span className="font-mono font-bold text-gray-900">{s.fitScore}</span>
              </div>
              <div className="flex-1">
                <div className="w-full bg-gray-100 rounded-full h-2">
                  <div className={`h-2 rounded-full ${fitColor(s.fitScore)}`} style={{ width: `${s.fitScore}%` }} />
                </div>
              </div>
            </div>
            <p className="text-[10px] text-gray-400 mt-2 ml-36">{s.note}</p>
          </div>
        ))}
      </div>

      {/* Teammate Dependency */}
      <SectionHeader title="Teammate Dependency Analysis" tag="ON-COURT NRTG BY CONTEXT" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-2">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">Spacing Impact</p>
          <div className="flex justify-between items-end">
            <div>
              <p className="text-[10px] text-gray-500">Elite-Spacing Lineups</p>
              <p className={`text-xl font-mono font-bold ${nrtgColor(p.teammateDependency.eliteSpacingNetRtg)}`}>
                {formatNrtg(p.teammateDependency.eliteSpacingNetRtg)}
              </p>
              <p className="text-[10px] text-gray-400 font-mono">{formatMinutes(p.teammateDependency.eliteSpacingMinutes)}</p>
            </div>
            <div className="text-center">
              <p className={`text-sm font-mono font-bold ${nrtgColor(p.teammateDependency.spacingDelta)}`}>
                &#916; {formatNrtg(p.teammateDependency.spacingDelta)}
              </p>
            </div>
            <div className="text-right">
              <p className="text-[10px] text-gray-500">Poor-Spacing Lineups</p>
              <p className={`text-xl font-mono font-bold ${nrtgColor(p.teammateDependency.poorSpacingNetRtg)}`}>
                {formatNrtg(p.teammateDependency.poorSpacingNetRtg)}
              </p>
              <p className="text-[10px] text-gray-400 font-mono">{formatMinutes(p.teammateDependency.poorSpacingMinutes)}</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">Rim Protector Impact</p>
          <div className="flex justify-between items-end">
            <div>
              <p className="text-[10px] text-gray-500">With Rim Protector</p>
              <p className={`text-xl font-mono font-bold ${nrtgColor(p.teammateDependency.withRimProtectorNetRtg)}`}>
                {formatNrtg(p.teammateDependency.withRimProtectorNetRtg)}
              </p>
              <p className="text-[10px] text-gray-400 font-mono">{formatMinutes(p.teammateDependency.withRimProtectorMinutes)}</p>
            </div>
            <div className="text-right">
              <p className="text-[10px] text-gray-500">Without Rim Protector</p>
              <p className={`text-xl font-mono font-bold ${nrtgColor(p.teammateDependency.withoutRimProtectorNetRtg)}`}>
                {formatNrtg(p.teammateDependency.withoutRimProtectorNetRtg)}
              </p>
              <p className="text-[10px] text-gray-400 font-mono">{formatMinutes(p.teammateDependency.withoutRimProtectorMinutes)}</p>
            </div>
          </div>
        </div>
      </div>
      <p className="text-[10px] text-gray-400 mb-4">
        Dependency Score: {p.teammateDependency.dependencyScore}/100 (lower = more portable). Buckets with &lt; 50 min are shown as &ldquo;N/A&rdquo;.
      </p>

      {/* Advanced Signals — derived stats built on top of existing data sections. */}
      {hasAdvancedSignals && (
        <>
          <SectionHeader title="Advanced Signals" tag="DERIVED METRICS" />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
            {fe && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">
                  Friction Efficiency
                  <span className="ml-2 normal-case tracking-normal text-gray-400">eFG% by defender distance</span>
                </p>
                <div className="space-y-2 mb-3">
                  {[
                    { label: '0-2 ft (Very Tight)', value: fe.veryTightEfg },
                    { label: '2-4 ft (Tight)', value: fe.tightEfg },
                    { label: '4-6 ft (Open)', value: fe.openEfg },
                    { label: '6+ ft (Wide Open)', value: fe.wideOpenEfg },
                  ].map((row) => (
                    <div key={row.label} className="flex items-center gap-3">
                      <span className="w-28 text-[10px] text-gray-500">{row.label}</span>
                      <div className="flex-1 bg-gray-100 rounded-full h-2">
                        <div
                          className="h-2 rounded-full bg-primary-600"
                          style={{ width: pctWidth(row.value, 0.75) }}
                        />
                      </div>
                      <span className="w-12 text-right font-mono text-xs text-gray-900">
                        {(row.value * 100).toFixed(1)}%
                      </span>
                    </div>
                  ))}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <StatBox
                    label="Friction Slope"
                    value={formatSignedPct(fe.frictionSlope * 100)}
                    subtitle="wide-open − very-tight eFG"
                  />
                  <StatBox
                    label="Pressure-Adj eFG%"
                    value={`${(fe.pressureAdjustedEfg * 100).toFixed(1)}%`}
                    subtitle="avg across all buckets"
                  />
                </div>
              </div>
            )}

            {gi && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">
                  Gravity Index
                  <span className="ml-2 normal-case tracking-normal text-gray-400">proxy: tight-coverage + on/off lift</span>
                </p>
                <div className="flex items-center gap-4 mb-3">
                  <div className="flex-1">
                    <div className="w-full bg-gray-100 rounded-full h-3">
                      <div
                        className={`h-3 rounded-full ${fitColor(gi.gravityIndex)}`}
                        style={{ width: `${gi.gravityIndex}%` }}
                      />
                    </div>
                  </div>
                  <span className="text-2xl font-mono font-bold text-gray-900 w-16 text-right">
                    {gi.gravityIndex.toFixed(1)}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <StatBox
                    label="Tight Coverage Rate"
                    value={`${(gi.tightAttentionRate * 100).toFixed(1)}%`}
                    subtitle="FGA with defender ≤ 4 ft"
                  />
                  <StatBox
                    label="Team ORtg Lift"
                    value={formatSignedPct(gi.teamOffLift)}
                    subtitle="on − off court"
                  />
                </div>
                <p className="text-[10px] text-gray-400 mt-3">
                  Proxy — direct teammate CS3 defender-distance on/off isn&apos;t exposed by NBA Stats.
                </p>
              </div>
            )}

            {sd && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">
                  Shot Diet Entropy
                  <span className="ml-2 normal-case tracking-normal text-gray-400">scheme-proof vs specialist</span>
                </p>
                <div className="flex items-center gap-4 mb-3">
                  <div className="flex-1">
                    <div className="w-full bg-gray-100 rounded-full h-3">
                      <div
                        className={`h-3 rounded-full ${fitColor(sd.entropyNormalized * 100)}`}
                        style={{ width: `${sd.entropyNormalized * 100}%` }}
                      />
                    </div>
                  </div>
                  <span className="text-2xl font-mono font-bold text-gray-900 w-20 text-right">
                    {(sd.entropyNormalized * 100).toFixed(0)}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <StatBox
                    label="Primary Modes"
                    value={sd.primaryModes}
                    subtitle="play types ≥ 10% freq"
                  />
                  <StatBox
                    label="Top Play Type"
                    value={sd.topPlayType || 'N/A'}
                    subtitle={`${(sd.topPlayTypeFreq * 100).toFixed(0)}% of possessions`}
                  />
                </div>
              </div>
            )}

            {rg && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">
                  Rim Gravity
                  <span className="ml-2 normal-case tracking-normal text-gray-400">how much you bend the D inward</span>
                </p>
                <div className="flex items-center gap-4 mb-3">
                  <div className="flex-1">
                    <div className="w-full bg-gray-100 rounded-full h-3">
                      <div
                        className={`h-3 rounded-full ${fitColor(rg.rimGravityScore)}`}
                        style={{ width: `${rg.rimGravityScore}%` }}
                      />
                    </div>
                  </div>
                  <span className="text-2xl font-mono font-bold text-gray-900 w-16 text-right">
                    {rg.rimGravityScore.toFixed(1)}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <StatBox label="Paint Touches/G" value={rg.paintTouchesPerGame.toFixed(1)} />
                  <StatBox label="Drives/G" value={rg.drivesPerGame.toFixed(1)} />
                  <StatBox
                    label="Rim FG%"
                    value={`${(rg.rimFgPct * 100).toFixed(1)}%`}
                    subtitle={`${formatSignedPct(rg.rimFgPctVsLeague * 100)} vs lg`}
                  />
                  <StatBox label="Paint Pts/Touch" value={rg.paintPtsPerTouch.toFixed(2)} />
                </div>
              </div>
            )}

            {lb && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">
                  Lineup Buoyancy
                  <span className="ml-2 normal-case tracking-normal text-gray-400">floor-raiser vs ceiling-raiser</span>
                </p>
                <div className="flex items-baseline justify-between mb-3">
                  <p className="text-sm font-semibold text-primary-700">{lb.buoyancyType}</p>
                  <p className="text-[10px] text-gray-400 font-mono">
                    {lb.totalLineups} lineups • {Math.round(lb.qualifyingMinutes)} min
                  </p>
                </div>
                <div className="space-y-2 mb-3">
                  <div className="flex items-center gap-3">
                    <span className="w-16 text-[10px] text-gray-500">Floor</span>
                    <div className="flex-1 bg-gray-100 rounded-full h-2">
                      <div className={`h-2 rounded-full ${fitColor(lb.floorScore)}`} style={{ width: `${lb.floorScore}%` }} />
                    </div>
                    <span className="w-14 text-right font-mono text-xs text-gray-900">{lb.floorScore.toFixed(0)}</span>
                  </div>
                  <div className="flex items-center gap-3">
                    <span className="w-16 text-[10px] text-gray-500">Ceiling</span>
                    <div className="flex-1 bg-gray-100 rounded-full h-2">
                      <div className={`h-2 rounded-full ${fitColor(lb.ceilingScore)}`} style={{ width: `${lb.ceilingScore}%` }} />
                    </div>
                    <span className="w-14 text-right font-mono text-xs text-gray-900">{lb.ceilingScore.toFixed(0)}</span>
                  </div>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <StatBox
                    label="Worst 1/3 NRtg"
                    value={formatNrtg(lb.worstTercileNetRtg)}
                    subtitle={`${Math.round(lb.worstTercileMinutes)} min`}
                  />
                  <StatBox
                    label="Best 1/3 NRtg"
                    value={formatNrtg(lb.bestTercileNetRtg)}
                    subtitle={`${Math.round(lb.bestTercileMinutes)} min`}
                  />
                </div>
                <p className="text-[10px] text-gray-400 mt-3">
                  Spread: {formatNrtg(lb.lineupSpread)} • Median: {formatNrtg(lb.medianLineupNetRtg)}
                </p>
              </div>
            )}

            {sr && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">
                  Scheme Robustness
                  <span className="ml-2 normal-case tracking-normal text-gray-400">PPP variance, top 3 play types</span>
                </p>
                <div className="flex items-center gap-4 mb-3">
                  <div className="flex-1">
                    <div className="w-full bg-gray-100 rounded-full h-3">
                      <div
                        className={`h-3 rounded-full ${fitColor(sr.robustnessScore)}`}
                        style={{ width: `${sr.robustnessScore}%` }}
                      />
                    </div>
                  </div>
                  <span className="text-2xl font-mono font-bold text-gray-900 w-16 text-right">
                    {sr.robustnessScore.toFixed(1)}
                  </span>
                </div>
                <div className="space-y-1.5 mb-3">
                  {sr.topPlayTypes.map((name, i) => {
                    const ppp = sr.topPlayTypePpps[i] ?? 0
                    return (
                      <div key={name} className="flex items-center gap-3 text-xs">
                        <span className="w-32 text-gray-700 capitalize">{name.replace(/_/g, ' ')}</span>
                        <div className="flex-1 bg-gray-100 rounded-full h-1.5">
                          <div
                            className="h-1.5 rounded-full bg-primary-600"
                            style={{ width: `${Math.min(100, (ppp / 1.5) * 100)}%` }}
                          />
                        </div>
                        <span className="w-14 text-right font-mono text-gray-900">{ppp.toFixed(2)} PPP</span>
                      </div>
                    )
                  })}
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <StatBox label="Mean PPP" value={sr.pppMean.toFixed(2)} />
                  <StatBox
                    label="CV"
                    value={sr.coefficientOfVariation.toFixed(3)}
                    subtitle="lower = scheme-proof"
                  />
                </div>
                <p className="text-[10px] text-gray-400 mt-3">
                  Collapse risk: {sr.collapseRiskScore.toFixed(1)}/100. High CV = one mode carries; others fall off.
                </p>
              </div>
            )}

            {lst && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">
                  Late-Season Trend
                  <span className="ml-2 normal-case tracking-normal text-gray-400">fatigue/engagement proxy</span>
                </p>
                <div className="flex items-center justify-between mb-3">
                  <div>
                    <p className="text-[10px] text-gray-500">First {lst.earlyGames} games</p>
                    <p className="text-xl font-mono font-bold text-gray-900">
                      {lst.earlyGameScore.toFixed(1)}
                    </p>
                    <p className="text-[10px] text-gray-400 font-mono">{lst.earlyMinutesAvg.toFixed(1)} mpg</p>
                  </div>
                  <div className="text-center">
                    <p className={`text-lg font-mono font-bold ${lst.trendDelta >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                      {lst.trendDelta >= 0 ? '+' : ''}{lst.trendDelta.toFixed(1)}
                    </p>
                    <p className="text-[10px] text-gray-500">Δ Game Score</p>
                  </div>
                  <div className="text-right">
                    <p className="text-[10px] text-gray-500">Last {lst.lateGames} games</p>
                    <p className="text-xl font-mono font-bold text-gray-900">
                      {lst.lateGameScore.toFixed(1)}
                    </p>
                    <p className="text-[10px] text-gray-400 font-mono">{lst.lateMinutesAvg.toFixed(1)} mpg</p>
                  </div>
                </div>
                <p className="text-[10px] text-gray-400">
                  Proxy — NBA Stats doesn&apos;t expose per-quarter tracking at ingest. Season-tails give the closest fatigue signal.
                </p>
              </div>
            )}

            {pf && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 lg:col-span-2">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">
                  Pass Funnel & Cascade Playmaking
                  <span className="ml-2 normal-case tracking-normal text-gray-400">creation conversion chain</span>
                </p>
                <div className="grid grid-cols-4 gap-2 mb-3">
                  {[
                    { label: 'Passes/G', value: pf.passesMade.toFixed(1) },
                    { label: 'Potential Ast', value: pf.potentialAst.toFixed(1) },
                    { label: 'Actual Ast', value: pf.ast.toFixed(1) },
                    { label: 'Secondary Ast', value: pf.secondaryAst.toFixed(1) },
                  ].map((s) => (
                    <div key={s.label} className="bg-gray-50 border border-gray-200 rounded px-3 py-2 text-center">
                      <p className="text-[10px] text-gray-500 uppercase tracking-wider">{s.label}</p>
                      <p className="text-lg font-mono font-bold text-gray-900">{s.value}</p>
                    </div>
                  ))}
                </div>
                <div className="grid grid-cols-4 gap-2">
                  <StatBox
                    label="Pass → Potential"
                    value={`${pf.passToPotentialPct.toFixed(1)}%`}
                    subtitle="% of passes that could be assists"
                  />
                  <StatBox
                    label="Potential → Actual"
                    value={`${pf.potentialToActualPct.toFixed(1)}%`}
                    subtitle="teammate shot conversion"
                  />
                  <StatBox
                    label="Pass → Assist"
                    value={`${pf.passToActualPct.toFixed(1)}%`}
                    subtitle="overall creation rate"
                  />
                  <StatBox
                    label="Cascade Rate"
                    value={`${pf.cascadeRate.toFixed(1)}%`}
                    subtitle="hockey assists per pass"
                  />
                </div>
              </div>
            )}
          </div>
        </>
      )}

      {/* Defensive Switchability */}
      <SectionHeader title="Defensive Switchability" />
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4">
        <div className="flex items-center gap-2 mb-4">
          {['PG', 'SG', 'SF', 'PF', 'C'].map((pos) => (
            <div key={pos} className={`w-12 h-12 rounded flex items-center justify-center text-xs font-mono border ${
              p.defensiveSwitchability.guardablePositions.includes(pos)
                ? 'bg-green-50 border-green-300 text-green-700'
                : 'bg-gray-50 border-gray-200 text-gray-400'
            }`}>{pos}</div>
          ))}
        </div>
        <div className="grid grid-cols-3 gap-3 mb-3">
          <StatBox label="Switch Score" value={p.defensiveSwitchability.switchScore} />
          <StatBox label="Perim DFG% Diff" value={`${p.defensiveSwitchability.perimeterDfgDiff > 0 ? '+' : ''}${p.defensiveSwitchability.perimeterDfgDiff.toFixed(1)}%`} />
          <StatBox label="PnR Navigation" value={p.defensiveSwitchability.pnrNavigation} />
        </div>
        <p className="text-sm text-gray-500">{p.defensiveSwitchability.scoutingNote}</p>
      </div>

      {/* Projected Team Fits */}
      <SectionHeader title="Projected Team Fits" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3 mb-4">
        {p.projectedFits.map((f) => (
          <div key={f.team} className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className="flex justify-between items-start mb-2">
              <div>
                <p className="text-sm text-gray-900 font-semibold">{f.team}</p>
                <p className="text-[10px] text-gray-500">{f.archetype}</p>
              </div>
              <span className="text-lg font-mono font-bold text-primary-600">{f.fitScore}</span>
            </div>
            <div className="flex gap-4 text-xs font-mono text-gray-500 mb-2">
              <span>Net: {f.projectedNetRtg > 0 ? '+' : ''}{f.projectedNetRtg.toFixed(1)}</span>
              <span className={f.deltaFromCurrent >= 0 ? 'text-green-600' : 'text-red-600'}>
                &#916; {f.deltaFromCurrent >= 0 ? '+' : ''}{f.deltaFromCurrent.toFixed(1)}
              </span>
            </div>
            <p className="text-[10px] text-gray-400">{f.reasoning}</p>
          </div>
        ))}
      </div>

      {/* Historical Comps */}
      <SectionHeader title="Historical Portability Comps" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {p.historicalComps.map((c) => (
          <div key={c.player} className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className="flex justify-between items-start mb-2">
              <p className="text-sm text-gray-900 font-semibold">{c.player}</p>
              <div className="text-right">
                <p className="text-xs font-mono text-primary-600">{c.similarity}% similar</p>
                <p className="text-xs font-mono text-gray-400">Port: {c.portabilityScore}</p>
              </div>
            </div>
            <p className="text-[10px] text-gray-400">{c.analysis}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
