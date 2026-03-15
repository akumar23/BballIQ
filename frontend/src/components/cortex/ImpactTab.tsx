import { BarChart, Bar, XAxis, YAxis, Cell, LabelList, ResponsiveContainer } from 'recharts'
import type { CortexPlayer } from '@/data/cortexTypes'
import { SectionHeader, StatBox } from './shared'

export default function ImpactTab({ player }: { player: CortexPlayer }) {
  const oo = player.impact.onOff
  const ctx = player.impact.contextualized
  const luck = player.impact.luck

  const impactModels = [
    { name: 'RAPM', value: player.impact.rapm },
    { name: 'RPM', value: player.impact.rpm },
    { name: 'EPM', value: player.impact.epm },
    { name: 'RAPTOR', value: player.impact.raptor },
    { name: 'LEBRON', value: player.impact.lebron },
    { name: 'DARKO', value: player.impact.darko },
  ]

  return (
    <div>
      {/* On/Off Court Splits */}
      <SectionHeader title="On/Off Court Splits" />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">Offense</p>
          <DiffBar label="ORtg On" value={oo.onORtg} />
          <DiffBar label="ORtg Off" value={oo.offORtg} />
          <p className="text-xs font-mono mt-2 text-green-600">+{(oo.onORtg - oo.offORtg).toFixed(1)} swing</p>
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">Defense</p>
          <DiffBar label="DRtg On" value={oo.onDRtg} invert />
          <DiffBar label="DRtg Off" value={oo.offDRtg} invert />
          <p className="text-xs font-mono mt-2 text-green-600">{(oo.onDRtg - oo.offDRtg).toFixed(1)} swing</p>
        </div>
        <div className="bg-primary-50 border border-primary-200 rounded-lg p-4 flex flex-col items-center justify-center">
          <p className="text-[10px] text-primary-600 uppercase tracking-wider">Total Net Swing</p>
          <p className="text-4xl font-mono font-bold text-primary-600 mt-1">+{oo.netSwing.toFixed(1)}</p>
        </div>
      </div>

      {/* Contextualized Net Rating */}
      <SectionHeader title="Contextualized Net Rating" tag="ISOLATED VALUE" />
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6 mb-4">
        <div className="flex items-center gap-8 mb-6">
          <div>
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">Raw Net Rtg</p>
            <p className="text-3xl font-mono font-bold text-gray-400 line-through">{ctx.rawNetRtg > 0 ? '+' : ''}{ctx.rawNetRtg.toFixed(1)}</p>
          </div>
          <span className="text-2xl text-gray-300">→</span>
          <div>
            <p className="text-[10px] text-primary-600 uppercase tracking-wider">Contextualized Net Rtg</p>
            <p className="text-3xl font-mono font-bold text-primary-600">{ctx.contextualizedNetRtg > 0 ? '+' : ''}{ctx.contextualizedNetRtg.toFixed(1)}</p>
          </div>
          <span className="ml-auto text-xs font-mono px-2 py-1 rounded bg-green-50 text-green-600">{ctx.percentile}th percentile</span>
        </div>

        {/* Adjustment Waterfall */}
        <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">Adjustment Waterfall</p>
        {ctx.adjustments.map((adj, i) => (
          <div key={adj.name} className="flex items-center gap-3 py-2 border-b border-gray-100 last:border-0">
            <div className="w-48 shrink-0">
              <p className="text-xs text-gray-700">{adj.name}</p>
            </div>
            <div className="w-20 text-right shrink-0">
              {i > 0 && (
                <span className={`text-sm font-mono font-bold ${adj.value >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                  {adj.value >= 0 ? '+' : ''}{adj.value.toFixed(1)}
                </span>
              )}
            </div>
            <div className="flex-1 mx-2">
              <div className="w-full bg-gray-100 rounded-full h-2 relative">
                <div
                  className="h-2 rounded-full bg-primary-600 transition-all"
                  style={{ width: `${Math.max(5, (adj.cumulative / ctx.rawNetRtg) * 100)}%` }}
                />
              </div>
            </div>
            <div className="w-16 text-right shrink-0">
              <span className="text-sm font-mono text-gray-900">{adj.cumulative > 0 ? '+' : ''}{adj.cumulative.toFixed(1)}</span>
            </div>
          </div>
        ))}
        <div className="mt-3">
          {ctx.adjustments.slice(1).map((adj) => (
            <p key={adj.name} className="text-[10px] text-gray-400 mt-1">&#8226; {adj.name}: {adj.explanation}</p>
          ))}
        </div>
      </div>

      {/* Opponent Tier Performance */}
      <SectionHeader title="Performance by Opponent Tier" tag="DIFFICULTY WEIGHTING" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-2">
        {player.opponentTier.map((t) => (
          <div key={t.tier} className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">{t.tier}</p>
            <p className={`text-2xl font-mono font-bold mt-1 ${t.netRtg >= 5 ? 'text-green-600' : t.netRtg >= 0 ? 'text-yellow-600' : 'text-red-600'}`}>
              {t.netRtg > 0 ? '+' : ''}{t.netRtg.toFixed(1)}
            </p>
            <div className="flex justify-between text-[10px] text-gray-400 font-mono mt-1">
              <span>{t.minutes} min</span>
              <span>{t.weight}x</span>
            </div>
          </div>
        ))}
      </div>
      <p className="text-[10px] text-gray-400 mb-4">Methodology: Opponent quality is ranked 1-250. Weight multiplier applied to net rating — elite opponents count more. This isolates performance against meaningful competition.</p>

      {/* Lineup Context */}
      <SectionHeader title="Lineup Context" tag="TEAMMATE ISOLATION" />
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden mb-4">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-[10px] text-gray-500 uppercase tracking-wider">
              <th className="text-left px-4 py-3">Lineup</th>
              <th className="text-right px-4 py-3">Min</th>
              <th className="text-right px-4 py-3">Raw Net</th>
              <th className="text-right px-4 py-3">Ctx Net</th>
              <th className="text-right px-4 py-3">Opp Tier</th>
            </tr>
          </thead>
          <tbody>
            {player.lineupContext.topLineups.map((l, i) => (
              <tr key={i} className="border-b border-gray-100 hover:bg-gray-50">
                <td className="px-4 py-2.5">
                  <div className="flex flex-wrap gap-1">
                    {l.players.map((p) => (
                      <span key={p} className={`text-xs px-1.5 py-0.5 rounded ${
                        p === player.name.split(' ').pop() || p === player.name.split(' ')[0] || p === player.id.toUpperCase()
                          ? 'bg-primary-500/10 text-primary-600' : 'text-gray-500'
                      }`}>{p}</span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-gray-700">{l.minutes}</td>
                <td className="px-4 py-2.5 text-right font-mono text-gray-700">{l.rawNet > 0 ? '+' : ''}{l.rawNet.toFixed(1)}</td>
                <td className="px-4 py-2.5 text-right font-mono font-bold text-primary-600">{l.ctxNet > 0 ? '+' : ''}{l.ctxNet.toFixed(1)}</td>
                <td className="px-4 py-2.5 text-right text-xs text-gray-500">{l.oppTier}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      <div className="bg-gray-50 border border-gray-200 rounded p-4 mb-4">
        <p className="text-[10px] text-gray-500 uppercase tracking-wider">Without Top Teammate</p>
        <p className="text-sm text-gray-700 mt-1">Without <span className="text-primary-600 font-semibold">{player.lineupContext.withoutTopTeammate.teammate}</span>:</p>
        <p className="text-2xl font-mono font-bold text-gray-900 mt-1">{player.lineupContext.withoutTopTeammate.netRtg > 0 ? '+' : ''}{player.lineupContext.withoutTopTeammate.netRtg.toFixed(1)} Net Rtg <span className="text-sm text-gray-500">({player.lineupContext.withoutTopTeammate.minutes} min)</span></p>
      </div>

      {/* Luck-Adjusted */}
      <SectionHeader title="Luck-Adjusted Metrics" />
      <div className="grid grid-cols-3 gap-3 mb-4">
        <StatBox label="Expected Wins" value={luck.xWins} subtitle={`Actual: ${luck.actualWins}`} />
        <StatBox label="Clutch EPA" value={luck.clutchEPA.toFixed(1)} />
        <StatBox label="Garbage Time Pts" value={`${luck.garbageTimePts.toFixed(1)}/g`} />
      </div>

      {/* Aggregate Impact Models */}
      <SectionHeader title="Aggregate Impact Models" />
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={impactModels} layout="vertical" margin={{ left: 60, right: 40 }}>
            <XAxis type="number" tick={{ fill: '#6b7280', fontSize: 11 }} axisLine={{ stroke: '#e5e7eb' }} />
            <YAxis type="category" dataKey="name" tick={{ fill: '#6b7280', fontSize: 12 }} axisLine={false} tickLine={false} />
            <Bar dataKey="value" radius={[0, 4, 4, 0]}>
              {impactModels.map((e, i) => (
                <Cell key={i} fill={e.value >= 0 ? '#2563eb' : '#ef4444'} />
              ))}
              <LabelList dataKey="value" position="right" formatter={(v: unknown) => Number(v).toFixed(1)} style={{ fill: '#374151', fontSize: 11 }} />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </div>
    </div>
  )
}

function DiffBar({ label, value, invert = false }: { label: string; value: number; invert?: boolean }) {
  const pct = Math.min(value / 1.3, 100)
  const color = invert ? (value < 110 ? 'bg-green-500' : 'bg-red-500') : (value > 110 ? 'bg-green-500' : 'bg-red-500')
  return (
    <div className="mb-2">
      <div className="flex justify-between text-xs mb-1">
        <span className="text-gray-500">{label}</span>
        <span className="font-mono text-gray-900">{value.toFixed(1)}</span>
      </div>
      <div className="w-full bg-gray-100 rounded-full h-2">
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
