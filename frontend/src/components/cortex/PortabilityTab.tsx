import type { CortexPlayer } from '@/data/cortexTypes'
import { SectionHeader, StatBox, fitColor } from './shared'

export default function PortabilityTab({ player }: { player: CortexPlayer }) {
  const p = player.portability

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
      <SectionHeader title="Teammate Dependency Analysis" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-2">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">Spacing Impact</p>
          <div className="flex justify-between items-end">
            <div>
              <p className="text-[10px] text-gray-500">Elite Spacing</p>
              <p className="text-xl font-mono font-bold text-green-600">{(p.teammateDependency.eliteSpacingTS * 100).toFixed(1)}%</p>
            </div>
            <div className="text-center">
              <p className="text-sm font-mono font-bold text-yellow-600">&#916; {p.teammateDependency.spacingDelta.toFixed(1)}</p>
            </div>
            <div className="text-right">
              <p className="text-[10px] text-gray-500">Poor Spacing</p>
              <p className="text-xl font-mono font-bold text-red-600">{(p.teammateDependency.poorSpacingTS * 100).toFixed(1)}%</p>
            </div>
          </div>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">Rim Protector Impact</p>
          <div className="flex justify-between items-end">
            <div>
              <p className="text-[10px] text-gray-500">With Rim Protector</p>
              <p className="text-xl font-mono font-bold text-green-600">{(p.teammateDependency.withRimProtectorFg * 100).toFixed(1)}%</p>
            </div>
            <div className="text-right">
              <p className="text-[10px] text-gray-500">Without</p>
              <p className="text-xl font-mono font-bold text-red-600">{(p.teammateDependency.withoutRimProtectorFg * 100).toFixed(1)}%</p>
            </div>
          </div>
        </div>
      </div>
      <p className="text-[10px] text-gray-400 mb-4">Dependency Score: {p.teammateDependency.dependencyScore}/100 (lower = more portable)</p>

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
