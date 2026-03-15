import type { CortexPlayer } from '@/data/cortexTypes'
import { SectionHeader, DiffBadge, pppColor } from './shared'

const PLAY_TYPE_LABELS: Record<string, string> = {
  iso: 'Isolation', pnr_ball: 'PnR Ball Handler', spot_up: 'Spot Up', transition: 'Transition',
  post_up: 'Post Up', cut: 'Cut', off_screen: 'Off Screen', handoff: 'Handoff',
}

export default function OffenseTab({ player }: { player: CortexPlayer }) {
  const playTypes = Object.entries(player.playtype)

  return (
    <div>
      {/* Play Type Breakdown */}
      <SectionHeader title="Play Type Breakdown" />
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-[10px] text-gray-500 uppercase tracking-wider">
              <th className="text-left px-4 py-3">Play Type</th>
              <th className="text-right px-4 py-3">Freq %</th>
              <th className="text-left px-4 py-3 w-24">Dist</th>
              <th className="text-right px-4 py-3">PPP</th>
              <th className="text-right px-4 py-3">eFG%</th>
              <th className="text-right px-4 py-3">Rank</th>
            </tr>
          </thead>
          <tbody>
            {playTypes.map(([key, pt]) => (
              <tr key={key} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                <td className="px-4 py-2.5 text-gray-900">{PLAY_TYPE_LABELS[key] || key}</td>
                <td className="px-4 py-2.5 text-right font-mono text-gray-700">{pt.freq.toFixed(1)}%</td>
                <td className="px-4 py-2.5">
                  <div className="w-full bg-gray-100 rounded-full h-1.5">
                    <div className="bg-primary-600 h-1.5 rounded-full" style={{ width: `${Math.min(pt.freq * 3, 100)}%` }} />
                  </div>
                </td>
                <td className={`px-4 py-2.5 text-right font-mono font-bold ${pppColor(pt.ppp)}`}>{pt.ppp.toFixed(2)}</td>
                <td className="px-4 py-2.5 text-right font-mono text-gray-700">{(pt.efg * 100).toFixed(1)}%</td>
                <td className="px-4 py-2.5 text-right font-mono text-gray-400">{pt.rank || '—'}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      {/* Shot Zone Distribution */}
      <SectionHeader title="Shot Zone Distribution" />
      <div className="grid grid-cols-2 sm:grid-cols-3 lg:grid-cols-6 gap-3">
        {player.shotZones.map((z) => {
          const diff = z.fgPct - z.leagueAvg
          return (
            <div key={z.zone} className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
              <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">{z.zone}</p>
              <p className="text-2xl font-mono font-bold text-gray-900">{(z.fgPct * 100).toFixed(1)}%</p>
              <div className="flex items-center justify-between mt-2 text-[10px] text-gray-500 font-mono">
                <span>{z.fga.toFixed(1)} FGA</span>
                <span>{z.freq.toFixed(1)}%</span>
              </div>
              <div className="mt-2">
                <DiffBadge value={diff * 100} />
              </div>
            </div>
          )
        })}
      </div>
    </div>
  )
}
