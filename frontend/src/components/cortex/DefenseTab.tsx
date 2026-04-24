import type { CortexPlayer } from '@/data/cortexTypes'
import { SectionHeader, StatBox, DiffBadge, qualityColor, fitColor } from './shared'

function formatSignedPct(value: number): string {
  const sign = value > 0 ? '+' : ''
  return `${sign}${value.toFixed(1)}%`
}

export default function DefenseTab({ player }: { player: CortexPlayer }) {
  const d = player.defensive
  const o = d.overview
  const terrain = player.defensiveTerrain
  const cc = player.contestConversion
  const hasAdvancedDefense = Boolean(terrain || cc)

  return (
    <div>
      {/* Defensive Overview */}
      <SectionHeader title="Defensive Overview" tag="IMPACT" />
      <div className="grid grid-cols-3 sm:grid-cols-4 lg:grid-cols-7 gap-2">
        <StatBox label="D-RAPM" value={o.dRapm.toFixed(1)} subtitle={`Rank #${o.rank}`} />
        <StatBox label="Contest Rate" value={`${o.contestRate.toFixed(1)}%`} />
        <StatBox label="DFG% Diff" value={`${o.dfgPctDiff > 0 ? '+' : ''}${o.dfgPctDiff.toFixed(1)}%`} />
        <StatBox label="STL Rate" value={`${o.stlRate.toFixed(1)}%`} />
        <StatBox label="BLK Rate" value={`${o.blkRate.toFixed(1)}%`} />
        <StatBox label="Deflections" value={o.deflections.toFixed(1)} subtitle="per game" />
        <StatBox label="DEF Rank" value={`#${o.rank}`} />
      </div>

      {/* Perimeter Defense */}
      <SectionHeader title="Perimeter Defense" tag="ON-BALL TRACKING" />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-3 mb-4">
        {[
          { label: 'On-Ball DFG%', val: d.perimeter.onBallDfg, diff: d.perimeter.onBallDfgDiff },
          { label: 'Pull-Up DFG%', val: d.perimeter.pullUpDfg, diff: d.perimeter.pullUpDfgDiff },
          { label: 'Catch & Shoot DFG%', val: d.perimeter.catchShootDfg, diff: d.perimeter.catchShootDfgDiff },
        ].map((s) => (
          <div key={s.label} className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">{s.label}</p>
            <p className="text-3xl font-mono font-bold text-gray-900 mt-1">{s.val.toFixed(1)}%</p>
            <DiffBadge value={s.diff} />
          </div>
        ))}
      </div>

      <div className="grid grid-cols-2 lg:grid-cols-4 gap-2 mb-4">
        {[
          { label: 'Tight Contest Rate', val: d.perimeter.tightContestRate, good: 70, ok: 55 },
          { label: 'Screen Nav Rate', val: d.perimeter.screenNavRate, good: 75, ok: 60 },
          { label: 'Avg Contest Dist', val: d.perimeter.avgContestDist, good: 0, ok: 0 },
          { label: 'Dribble % Allowed', val: d.perimeter.dribblePctAllowed, good: 0, ok: 0 },
        ].map((s) => (
          <div key={s.label} className="bg-gray-50 border border-gray-200 rounded px-4 py-3">
            <p className="text-[10px] text-gray-500 uppercase tracking-wider">{s.label}</p>
            <p className={`text-xl font-mono font-bold mt-0.5 ${s.good > 0 ? qualityColor(s.val, { good: s.good, ok: s.ok }) : 'text-gray-900'}`}>
              {s.label.includes('Dist') ? `${s.val.toFixed(1)} ft` : `${s.val.toFixed(1)}%`}
            </p>
          </div>
        ))}
      </div>

      <div className="bg-gray-50 border border-gray-200 rounded p-4">
        <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Scouting Report</p>
        <p className="text-sm text-gray-600 leading-relaxed">{d.perimeter.scoutingReport}</p>
      </div>

      {/* Isolation Defense */}
      <SectionHeader title="Isolation Defense" tag="1-ON-1" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
        <div className="grid grid-cols-3 gap-2">
          <StatBox label="ISO DFG%" value={`${d.isolation.isoDfg.toFixed(1)}%`} />
          <StatBox label="ISO PPP" value={d.isolation.isoPpp.toFixed(2)} />
          <StatBox label="ISO Rank" value={`#${d.isolation.isoRank}`} />
          <StatBox label="Possessions" value={d.isolation.possessions} />
          <StatBox label="TOV Forced %" value={`${d.isolation.tovForcedPct.toFixed(1)}%`} />
          <StatBox label="Freq Targeted" value={`${d.isolation.freqTargeted.toFixed(1)}%`} />
        </div>
        <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
          <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">ISO Defense by Zone</p>
          {d.isolation.byZone.map((z) => (
            <div key={z.zone} className="mb-3">
              <div className="flex justify-between text-xs mb-1">
                <span className="text-gray-600">{z.zone}</span>
                <span className="font-mono text-gray-700">{z.dfgPct.toFixed(1)}% <span className="text-gray-400">({z.freq}%)</span></span>
              </div>
              <div className="w-full bg-gray-100 rounded-full h-2">
                <div
                  className={`h-2 rounded-full ${z.dfgPct < 40 ? 'bg-green-500' : z.dfgPct < 48 ? 'bg-yellow-500' : 'bg-red-500'}`}
                  style={{ width: `${z.dfgPct}%` }}
                />
              </div>
            </div>
          ))}
        </div>
      </div>
      <div className="bg-gray-50 border border-gray-200 rounded p-4 mb-4">
        <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-2">Scouting Report</p>
        <p className="text-sm text-gray-600 leading-relaxed">{d.isolation.scoutingReport}</p>
      </div>

      {/* Rim Protection */}
      <SectionHeader title="Rim Protection" />
      <div className="grid grid-cols-3 gap-3 mb-4">
        <StatBox label="Contests/G" value={d.rimProtection.contestsPerGame.toFixed(1)} className="text-center" />
        <StatBox label="DFG% at Rim" value={`${d.rimProtection.dfgPctAtRim.toFixed(1)}%`} className="text-center" />
        <StatBox label="Diff vs League" value={`${d.rimProtection.diffVsLeague > 0 ? '+' : ''}${d.rimProtection.diffVsLeague.toFixed(1)}%`} className="text-center" />
      </div>

      {/* Opponent Shooting */}
      {player.opponentShooting && player.opponentShooting.buckets.length > 0 && (
        <>
          <SectionHeader title="Opponent Shooting" tag="DEFENSIVE" />
          <p className="text-xs text-gray-500 mb-3 font-mono">{player.opponentShooting.games} games</p>
          <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden mb-4">
            <table className="w-full text-sm">
              <thead>
                <tr className="border-b border-gray-200 text-[10px] text-gray-500 uppercase tracking-wider">
                  <th className="text-left px-4 py-3">Distance</th>
                  <th className="text-right px-4 py-3">Defended FGA</th>
                  <th className="text-right px-4 py-3">DFG%</th>
                  <th className="text-right px-4 py-3">Normal FG%</th>
                  <th className="text-right px-4 py-3">Diff</th>
                </tr>
              </thead>
              <tbody>
                {player.opponentShooting.buckets.map((b) => (
                  <tr key={b.label} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                    <td className="px-4 py-2.5 text-gray-900">{b.label}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-gray-700">{b.defendedFga.toFixed(1)}</td>
                    <td className="px-4 py-2.5 text-right font-mono text-gray-700">{(b.defendedFgPct * 100).toFixed(1)}%</td>
                    <td className="px-4 py-2.5 text-right font-mono text-gray-700">{(b.normalFgPct * 100).toFixed(1)}%</td>
                    <td className="px-4 py-2.5 text-right">
                      <DiffBadge value={b.pctPlusminus * 100} label="vs Avg" />
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </>
      )}

      {hasAdvancedDefense && (
        <>
          <SectionHeader title="Advanced Defense Signals" tag="DERIVED METRICS" />
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-4 mb-4">
            {terrain && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">
                  Defensive Terrain
                  <span className="ml-2 normal-case tracking-normal text-gray-400">zone-weighted stopping power</span>
                </p>
                <div className="flex items-center gap-4 mb-3">
                  <div className="flex-1">
                    <div className="w-full bg-gray-100 rounded-full h-3">
                      <div
                        className={`h-3 rounded-full ${fitColor(terrain.terrainScore)}`}
                        style={{ width: `${terrain.terrainScore}%` }}
                      />
                    </div>
                  </div>
                  <span className="text-2xl font-mono font-bold text-gray-900 w-16 text-right">
                    {terrain.terrainScore.toFixed(1)}
                  </span>
                </div>
                <div className="space-y-2">
                  {[
                    { label: 'Rim', freq: terrain.rimFreq, pm: terrain.rimPlusMinus, contrib: terrain.rimContribution },
                    { label: 'Mid', freq: terrain.midFreq, pm: terrain.midPlusMinus, contrib: terrain.midContribution },
                    { label: '3PT', freq: terrain.threeFreq, pm: terrain.threePlusMinus, contrib: terrain.threeContribution },
                  ].map((row) => {
                    const good = row.contrib > 0
                    return (
                      <div key={row.label} className="flex items-center gap-3 text-xs">
                        <span className="w-10 text-gray-600 font-medium">{row.label}</span>
                        <span className="w-16 text-right font-mono text-gray-500">
                          {(row.freq * 100).toFixed(1)}%
                        </span>
                        <span className={`w-20 text-right font-mono font-bold ${good ? 'text-green-600' : 'text-red-600'}`}>
                          {formatSignedPct(row.pm * 100)}
                        </span>
                        <div className="flex-1 bg-gray-100 rounded-full h-1.5">
                          <div
                            className={`h-1.5 rounded-full ${good ? 'bg-green-500' : 'bg-red-500'}`}
                            style={{ width: `${Math.min(100, Math.abs(row.contrib) / 0.04 * 100)}%` }}
                          />
                        </div>
                      </div>
                    )
                  })}
                </div>
                <p className="text-[10px] text-gray-400 mt-3">
                  Each row = frequency × (−opp FG% vs league). Negative opp FG% diff = suppression (good).
                </p>
              </div>
            )}

            {cc && (
              <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-4">
                <p className="text-[10px] text-gray-500 uppercase tracking-wider mb-3">
                  Contest-to-Miss Conversion
                  <span className="ml-2 normal-case tracking-normal text-gray-400">volume × efficiency</span>
                </p>
                <div className="flex items-center gap-4 mb-3">
                  <div className="flex-1">
                    <div className="w-full bg-gray-100 rounded-full h-3">
                      <div
                        className={`h-3 rounded-full ${fitColor(cc.contestToMissScore)}`}
                        style={{ width: `${cc.contestToMissScore}%` }}
                      />
                    </div>
                  </div>
                  <span className="text-2xl font-mono font-bold text-gray-900 w-16 text-right">
                    {cc.contestToMissScore.toFixed(1)}
                  </span>
                </div>
                <div className="grid grid-cols-2 gap-3">
                  <StatBox label="Contests / G" value={cc.contestsPerGame.toFixed(1)} />
                  <StatBox
                    label="Defended FGA / G"
                    value={cc.defendedFgaPerGame.toFixed(1)}
                    subtitle="as nearest D"
                  />
                  <StatBox
                    label="Misses / G"
                    value={cc.missesForcedPerGame.toFixed(1)}
                    subtitle="primary-D only"
                  />
                  <StatBox
                    label="Miss Rate"
                    value={`${(cc.missRate * 100).toFixed(1)}%`}
                    subtitle="of defended FGA"
                  />
                </div>
                <p className="text-[10px] text-gray-400 mt-3">
                  Contests include help-side; defended FGA only counts primary coverage.
                </p>
              </div>
            )}
          </div>
        </>
      )}

      {/* Key Matchup Log */}
      <SectionHeader title="Key Matchup Log" />
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-gray-200 text-[10px] text-gray-500 uppercase tracking-wider">
              <th className="text-left px-4 py-3">Opponent</th>
              <th className="text-right px-4 py-3">Poss</th>
              <th className="text-right px-4 py-3">DFG%</th>
              <th className="text-right px-4 py-3">Pts Allowed</th>
            </tr>
          </thead>
          <tbody>
            {d.matchupLog.map((m) => (
              <tr key={m.opponent} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                <td className="px-4 py-2.5 text-gray-900">{m.opponent}</td>
                <td className="px-4 py-2.5 text-right font-mono text-gray-700">{m.possessions}</td>
                <td className={`px-4 py-2.5 text-right font-mono font-bold ${m.dfgPct < 40 ? 'text-green-600' : m.dfgPct < 48 ? 'text-yellow-600' : 'text-red-600'}`}>{m.dfgPct.toFixed(1)}%</td>
                <td className="px-4 py-2.5 text-right font-mono text-gray-700">{m.ptsAllowed}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  )
}
