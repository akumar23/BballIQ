import type { CortexPlayer } from '@/data/cortexTypes'
import { SectionHeader, StatBox, fitColor } from './shared'

export default function ChampionshipTab({ player }: { player: CortexPlayer }) {
  const c = player.championship

  return (
    <div>
      {/* Championship Index Hero */}
      <SectionHeader title="Championship Index" tag="RING PROBABILITY" />
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-4">
        <div className="flex flex-col lg:flex-row items-center gap-8">
          <svg width="180" height="180" viewBox="0 0 180 180">
            <circle cx="90" cy="90" r="74" fill="none" stroke="#e5e7eb" strokeWidth="10" />
            <circle cx="90" cy="90" r="74" fill="none" stroke="#2563eb" strokeWidth="10"
              strokeDasharray={`${(c.index / 100) * 465} 465`}
              strokeLinecap="round" transform="rotate(-90 90 90)" />
            <text x="90" y="82" textAnchor="middle" className="fill-gray-900 text-4xl font-mono font-bold">{c.index}</text>
            <text x="90" y="105" textAnchor="middle" className="fill-gray-500 text-[10px] font-mono">/100</text>
          </svg>
          <div className="flex-1">
            <p className="text-xs font-mono text-primary-600 tracking-widest mb-2">{c.tier}</p>
            <p className="text-sm text-gray-500 leading-relaxed">{c.verdict}</p>
          </div>
        </div>
        <div className="grid grid-cols-3 gap-3 mt-6">
          <StatBox label="Win Prob / Season" value={`${c.winProbability}%`} />
          <StatBox label="Historical Base Rate" value={`${c.historicalBaseRate}%`} subtitle="any #1 option" />
          <StatBox label="Multiplier vs Base" value={`${c.multiplier}x`} />
        </div>
      </div>

      {/* Championship Pillars */}
      <SectionHeader title="Championship Pillars" />
      <div className="space-y-2 mb-4">
        {c.pillars.map((p) => (
          <div key={p.name} className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className="flex items-center gap-4 mb-2">
              <div className="w-52 shrink-0">
                <p className="text-sm text-gray-900">{p.name}</p>
              </div>
              <div className="w-12 shrink-0 text-right">
                <span className="font-mono font-bold text-gray-900">{p.score}</span>
              </div>
              <div className="w-12 shrink-0 text-right">
                <span className="text-[10px] font-mono text-gray-500">{p.weight}%</span>
              </div>
              <div className="flex-1">
                <div className="w-full bg-gray-100 rounded-full h-2">
                  <div className={`h-2 rounded-full ${fitColor(p.score)}`} style={{ width: `${p.score}%` }} />
                </div>
              </div>
            </div>
            <p className="text-[10px] text-gray-400 ml-64">{p.explanation}</p>
          </div>
        ))}
      </div>

      {/* Playoff Projection */}
      <SectionHeader title="Playoff Performance Projection" />
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4 mb-4">
        <div className="grid grid-cols-4 gap-3 mb-4">
          {[
            { label: 'PPG', proj: c.playoffProjection.ppg, drop: c.playoffProjection.regToPlayoffDrop.ppg },
            { label: 'TS%', proj: c.playoffProjection.ts, drop: c.playoffProjection.regToPlayoffDrop.ts },
            { label: 'AST', proj: c.playoffProjection.ast, drop: c.playoffProjection.regToPlayoffDrop.ast },
            { label: 'DRtg', proj: c.playoffProjection.drtg, drop: c.playoffProjection.regToPlayoffDrop.drtg },
          ].map((s) => (
            <div key={s.label} className="text-center">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider">{s.label}</p>
              <p className="text-2xl font-mono font-bold text-gray-900 mt-1">
                {s.label === 'TS%' ? (s.proj * 100).toFixed(1) : s.proj.toFixed(1)}
              </p>
              <p className={`text-[10px] font-mono mt-1 ${s.drop <= 0 ? 'text-red-600' : s.label === 'DRtg' ? 'text-red-600' : 'text-green-600'}`}>
                {s.label === 'TS%' ? (s.drop * 100).toFixed(1) : s.drop > 0 ? `+${s.drop.toFixed(1)}` : s.drop.toFixed(1)} reg→playoff
              </p>
            </div>
          ))}
        </div>
        <p className="text-[10px] text-gray-400">{c.playoffProjection.comparisonNote}</p>
      </div>

      {/* Supporting Cast */}
      <SectionHeader title="Supporting Cast Requirements" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-2">
        <StatBox label="Min 2nd Option" value={c.supportingCast.min2ndOption} />
        <StatBox label="Spacing Need" value={c.supportingCast.spacingNeed} />
        <StatBox label="Defensive Need" value={c.supportingCast.defensiveNeed} />
        <StatBox label="Cap Flexibility" value={c.supportingCast.capFlexibility} />
      </div>
      <div className="bg-primary-50 border border-primary-200 rounded-lg p-4 mb-4">
        <p className="text-[10px] text-primary-600 uppercase tracking-wider mb-1">Blueprint</p>
        <p className="text-sm text-gray-700">{c.supportingCast.blueprint}</p>
      </div>

      {/* Comparables */}
      <SectionHeader title="Championship Run Comparables" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {c.comparables.map((comp) => (
          <div key={`${comp.player}-${comp.year}`} className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <div className="flex justify-between items-start mb-2">
              <div>
                <p className="text-sm text-gray-900 font-semibold">{comp.player} ({comp.year})</p>
                <p className="text-[10px] text-gray-500">{comp.role}</p>
              </div>
              <span className="text-lg">{comp.won ? '🏆' : '✗'}</span>
            </div>
            <div className="flex gap-4 text-xs font-mono text-gray-500 mb-2">
              <span>Cast: {comp.castStrength}</span>
              <span>Index: {comp.championshipIndex}</span>
            </div>
            <p className="text-[10px] text-gray-400">{comp.analysis}</p>
          </div>
        ))}
      </div>
    </div>
  )
}
