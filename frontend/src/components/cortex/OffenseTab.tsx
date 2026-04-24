import type { CortexPlayer } from '@/data/cortexTypes'
import { SectionHeader, StatBox, DiffBadge, pppColor, fitColor } from './shared'

function formatSignedPct(value: number): string {
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

const PLAY_TYPE_LABELS: Record<string, string> = {
  iso: 'Isolation', pnr_ball: 'PnR Ball Handler', spot_up: 'Spot Up', transition: 'Transition',
  post_up: 'Post Up', cut: 'Cut', off_screen: 'Off Screen', handoff: 'Handoff',
}

export default function OffenseTab({ player }: { player: CortexPlayer }) {
  const playTypes = Object.entries(player.playtype)
  const lev = player.leverageTs
  const dwell = player.possessionDwell
  const mile = player.mileProduction
  const hasAdvancedOffense = Boolean(lev || dwell || mile)

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

      {/* Touches Breakdown */}
      {player.touchesBreakdown && (
        <>
          <SectionHeader title="Touches Breakdown" />
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-[10px] text-gray-500 uppercase tracking-wider">
                  <th className="text-left px-4 py-3">Area</th>
                  <th className="text-right px-4 py-3">Touches</th>
                  <th className="text-right px-4 py-3">FGA</th>
                  <th className="text-right px-4 py-3">FG%</th>
                  <th className="text-right px-4 py-3">FTA</th>
                  <th className="text-right px-4 py-3">PTS</th>
                  <th className="text-right px-4 py-3">Passes</th>
                  <th className="text-right px-4 py-3">AST</th>
                  <th className="text-right px-4 py-3">TOV</th>
                  <th className="text-right px-4 py-3">Fouls</th>
                  <th className="text-right px-4 py-3">Pts/Touch</th>
                </tr>
              </thead>
              <tbody>
                {(
                  [
                    ['Elbow', player.touchesBreakdown.elbow],
                    ['Post', player.touchesBreakdown.post],
                    ['Paint', player.touchesBreakdown.paint],
                  ] as const
                )
                  .filter(([, row]) => row != null)
                  .map(([label, row]) => (
                    <tr key={label} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                      <td className="px-4 py-2.5 text-gray-900">{label}</td>
                      <td className="px-4 py-2.5 text-right font-mono text-gray-700">{row!.touches.toFixed(1)}</td>
                      <td className="px-4 py-2.5 text-right font-mono text-gray-700">{row!.fga.toFixed(1)}</td>
                      <td className="px-4 py-2.5 text-right font-mono text-gray-700">{(row!.fgPct * 100).toFixed(1)}%</td>
                      <td className="px-4 py-2.5 text-right font-mono text-gray-700">{row!.fta.toFixed(1)}</td>
                      <td className="px-4 py-2.5 text-right font-mono font-bold text-gray-900">{row!.pts.toFixed(1)}</td>
                      <td className="px-4 py-2.5 text-right font-mono text-gray-700">{row!.passes.toFixed(1)}</td>
                      <td className="px-4 py-2.5 text-right font-mono text-gray-700">{row!.ast.toFixed(1)}</td>
                      <td className="px-4 py-2.5 text-right font-mono text-gray-700">{row!.tov.toFixed(1)}</td>
                      <td className="px-4 py-2.5 text-right font-mono text-gray-700">{row!.fouls.toFixed(1)}</td>
                      <td className="px-4 py-2.5 text-right font-mono font-bold text-gray-900">{row!.ptsPerTouch.toFixed(2)}</td>
                    </tr>
                  ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {hasAdvancedOffense && (
        <>
          <SectionHeader title="Advanced Offense Signals" tag="DERIVED METRICS" />
          <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
            {lev && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">
                  Leverage TS%
                  <span className="ml-2 normal-case tracking-normal text-gray-400">blowouts stripped</span>
                </p>
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <StatBox label="Overall TS%" value={`${(lev.overallTs * 100).toFixed(1)}%`} />
                  <StatBox
                    label="Leverage TS%"
                    value={`${(lev.leverageTs * 100).toFixed(1)}%`}
                    subtitle={`${lev.leverageGames} games`}
                  />
                  <StatBox
                    label="Blowout TS%"
                    value={`${(lev.blowoutTs * 100).toFixed(1)}%`}
                    subtitle={`${lev.blowoutGames} games`}
                  />
                  <StatBox
                    label="Leverage Δ"
                    value={formatSignedPct(lev.tsLeverageDelta * 100)}
                    subtitle="vs overall"
                  />
                </div>
                <p className="text-[10px] text-gray-400">
                  &ldquo;Leverage&rdquo; = games with |plus/minus| ≤ 15. Positive delta = steps up in close games.
                </p>
              </div>
            )}

            {dwell && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">
                  Possession Dwell
                  <span className="ml-2 normal-case tracking-normal text-gray-400">output per ball-hold</span>
                </p>
                <div className="flex items-center gap-4 mb-3">
                  <div className="flex-1">
                    <div className="w-full bg-gray-100 rounded-full h-3">
                      <div
                        className={`h-3 rounded-full ${fitColor(dwell.dwellEfficiencyScore)}`}
                        style={{ width: `${dwell.dwellEfficiencyScore}%` }}
                      />
                    </div>
                  </div>
                  <span className="text-2xl font-mono font-bold text-gray-900 w-16 text-right">
                    {dwell.dwellEfficiencyScore.toFixed(1)}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <StatBox label="Sec / Touch" value={dwell.avgSecPerTouch.toFixed(2)} />
                  <StatBox label="Pts / Touch" value={dwell.ptsPerTouch.toFixed(3)} />
                  <StatBox label="Pts / Sec" value={dwell.ptsPerSecond.toFixed(3)} subtitle="with ball" />
                  <StatBox label="Create / Sec" value={dwell.creationPerSecond.toFixed(3)} subtitle="pts + 0.5×ast" />
                </div>
              </div>
            )}

            {mile && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">
                  Mile-Adjusted Production
                  <span className="ml-2 normal-case tracking-normal text-gray-400">(pts + ast) / mile</span>
                </p>
                <div className="grid grid-cols-2 gap-3 mb-3">
                  <StatBox
                    label="Dist / Game"
                    value={`${mile.distMilesPerGame.toFixed(2)} mi`}
                    subtitle={`${(mile.distMilesOffShare * 100).toFixed(0)}% offense`}
                  />
                  <StatBox label="Pts + Ast / G" value={mile.ptsAstPerGame.toFixed(1)} />
                  <StatBox
                    label="Per Mile"
                    value={mile.productionPerMile.toFixed(1)}
                    subtitle="full distance"
                  />
                  <StatBox
                    label="Per Off Mile"
                    value={mile.productionPerOffMile.toFixed(1)}
                    subtitle="offensive only"
                  />
                </div>
              </div>
            )}
          </div>
        </>
      )}
    </div>
  )
}
