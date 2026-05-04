import { BarChart, Bar, XAxis, YAxis, Cell, LabelList, ResponsiveContainer } from 'recharts'
import type { CortexPlayer } from '@/data/cortexTypes'
import Card from '@/components/ui/Card'
import SectionHeader from '@/components/ui/SectionHeader'
import Stat from '@/components/ui/Stat'
import { getChartTheme } from '@/lib/chartTheme'

export default function ImpactTab({ player }: { player: CortexPlayer }) {
  const oo = player.impact.onOff
  const ctx = player.impact.contextualized
  const luck = player.impact.luck
  const theme = getChartTheme()

  const impactModels = [
    { name: 'RAPM', value: player.impact.rapm },
    { name: 'RPM', value: player.impact.rpm },
    { name: 'EPM', value: player.impact.epm },
    { name: 'LEBRON', value: player.impact.lebron },
    { name: 'DARKO', value: player.impact.darko },
    { name: 'LAKER', value: player.impact.laker },
    { name: 'MAMBA', value: player.impact.mamba },
  ]

  return (
    <div>
      {/* On/Off Court Splits */}
      <SectionHeader title="On/Off Court Splits" />
      <div className="grid grid-cols-1 lg:grid-cols-3 gap-4 mb-4">
        <Card>
          <p className="text-micro text-text-muted uppercase tracking-wider mb-3">Offense</p>
          <DiffBar label="ORtg On" value={oo.onORtg} />
          <DiffBar label="ORtg Off" value={oo.offORtg} />
          <p className="text-caption font-mono tabular-nums mt-2 text-pos-strong dark:text-pos">
            +{(oo.onORtg - oo.offORtg).toFixed(1)} swing
          </p>
        </Card>
        <Card>
          <p className="text-micro text-text-muted uppercase tracking-wider mb-3">Defense</p>
          <DiffBar label="DRtg On" value={oo.onDRtg} invert />
          <DiffBar label="DRtg Off" value={oo.offDRtg} invert />
          <p className="text-caption font-mono tabular-nums mt-2 text-pos-strong dark:text-pos">
            {(oo.onDRtg - oo.offDRtg).toFixed(1)} swing
          </p>
        </Card>
        <Card className="bg-primary-50 dark:bg-primary-500/10 border-primary-200 dark:border-primary-500/30 flex flex-col items-center justify-center">
          <p className="text-micro text-primary-600 dark:text-primary-400 uppercase tracking-wider">
            Total Net Swing
          </p>
          <p className="text-display font-mono font-bold tabular-nums text-primary-600 dark:text-primary-400 mt-1">
            +{oo.netSwing.toFixed(1)}
          </p>
        </Card>
      </div>

      {/* Contextualized Net Rating */}
      <SectionHeader title="Contextualized Net Rating" tag="ISOLATED VALUE" />
      <Card padded={false} className="p-6 mb-4">
        <div className="flex items-center gap-8 mb-6">
          <div>
            <p className="text-micro text-text-muted uppercase tracking-wider">Raw Net Rtg</p>
            <p className="text-h1 font-mono font-bold tabular-nums text-text-muted line-through">
              {ctx.rawNetRtg > 0 ? '+' : ''}
              {ctx.rawNetRtg.toFixed(1)}
            </p>
          </div>
          <span className="text-h2 text-text-muted">→</span>
          <div>
            <p className="text-micro text-primary-600 dark:text-primary-400 uppercase tracking-wider">
              Contextualized Net Rtg
            </p>
            <p className="text-h1 font-mono font-bold tabular-nums text-primary-600 dark:text-primary-400">
              {ctx.contextualizedNetRtg > 0 ? '+' : ''}
              {ctx.contextualizedNetRtg.toFixed(1)}
            </p>
          </div>
          <span className="ml-auto text-caption font-mono tabular-nums px-2 py-1 rounded bg-pos-soft text-pos-strong dark:text-pos">
            {ctx.percentile}th percentile
          </span>
        </div>

        {/* Adjustment Waterfall */}
        <p className="text-micro text-text-muted uppercase tracking-wider mb-3">Adjustment Waterfall</p>
        {ctx.adjustments.map((adj, i) => (
          <div
            key={adj.name}
            className="flex items-center gap-3 py-2 border-b border-border-subtle last:border-0"
          >
            <div className="w-48 shrink-0">
              <p className="text-caption text-text-secondary">{adj.name}</p>
            </div>
            <div className="w-20 text-right shrink-0">
              {i > 0 && (
                <span
                  className={`text-body font-mono tabular-nums font-bold ${
                    adj.value >= 0
                      ? 'text-pos-strong dark:text-pos'
                      : 'text-neg-strong dark:text-neg'
                  }`}
                >
                  {adj.value >= 0 ? '+' : ''}
                  {adj.value.toFixed(1)}
                </span>
              )}
            </div>
            <div className="flex-1 mx-2">
              <div className="w-full bg-surface-3 rounded-full h-2 relative">
                <div
                  className="h-2 rounded-full bg-primary-600 dark:bg-primary-500 transition-all"
                  style={{ width: `${Math.max(5, (adj.cumulative / ctx.rawNetRtg) * 100)}%` }}
                />
              </div>
            </div>
            <div className="w-16 text-right shrink-0">
              <span className="text-body font-mono tabular-nums text-text-primary">
                {adj.cumulative > 0 ? '+' : ''}
                {adj.cumulative.toFixed(1)}
              </span>
            </div>
          </div>
        ))}
        <div className="mt-3">
          {ctx.adjustments.slice(1).map((adj) => (
            <p key={adj.name} className="text-micro text-text-muted mt-1">
              &#8226; {adj.name}: {adj.explanation}
            </p>
          ))}
        </div>
      </Card>

      {/* Opponent Tier Performance */}
      <SectionHeader title="Performance by Opponent Tier" tag="DIFFICULTY WEIGHTING" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-2">
        {player.opponentTier.map((t) => {
          const colorClass =
            t.netRtg >= 5
              ? 'text-pos-strong dark:text-pos'
              : t.netRtg >= 0
                ? 'text-warn-strong dark:text-warn'
                : 'text-neg-strong dark:text-neg'
          const glyph = t.netRtg >= 5 ? '\u25B2' : t.netRtg >= 0 ? '\u25B4' : '\u25BC'
          return (
            <Card key={t.tier}>
              <p className="text-micro text-text-muted uppercase tracking-wider">{t.tier}</p>
              <p className={`text-h2 font-mono font-bold tabular-nums mt-1 inline-flex items-center gap-1 ${colorClass}`}>
                <span aria-hidden="true">{glyph}</span>
                {t.netRtg > 0 ? '+' : ''}
                {t.netRtg.toFixed(1)}
              </p>
              <div className="flex justify-between text-micro text-text-muted font-mono tabular-nums mt-1">
                <span>{t.minutes} min</span>
                <span>{t.weight}x</span>
              </div>
            </Card>
          )
        })}
      </div>
      <p className="text-micro text-text-muted mb-4">
        Methodology: Opponent quality is ranked 1-250. Weight multiplier applied to net rating —
        elite opponents count more. This isolates performance against meaningful competition.
      </p>

      {/* Lineup Context */}
      <SectionHeader title="Lineup Context" tag="TEAMMATE ISOLATION" />
      <Card padded={false} className="overflow-hidden mb-4">
        <table className="w-full text-body tabular-nums">
          <thead>
            <tr className="border-b border-border-subtle text-micro text-text-muted uppercase tracking-wider">
              <th className="text-left px-4 py-3">Lineup</th>
              <th className="text-right px-4 py-3">Min</th>
              <th className="text-right px-4 py-3">Raw Net</th>
              <th className="text-right px-4 py-3">Ctx Net</th>
              <th className="text-right px-4 py-3">Opp Tier</th>
            </tr>
          </thead>
          <tbody>
            {player.lineupContext.topLineups.map((l, i) => (
              <tr
                key={i}
                className="border-b border-border-subtle/60 hover:bg-surface-3/70"
              >
                <td className="px-4 py-2.5">
                  <div className="flex flex-wrap gap-1">
                    {l.players.map((p) => (
                      <span
                        key={p}
                        className={`text-caption px-1.5 py-0.5 rounded ${
                          p === player.name.split(' ').pop() ||
                          p === player.name.split(' ')[0] ||
                          p === player.id.toUpperCase()
                            ? 'bg-primary-500/10 text-primary-600 dark:text-primary-400'
                            : 'text-text-muted'
                        }`}
                      >
                        {p}
                      </span>
                    ))}
                  </div>
                </td>
                <td className="px-4 py-2.5 text-right font-mono text-text-secondary">{l.minutes}</td>
                <td className="px-4 py-2.5 text-right font-mono text-text-secondary">
                  {l.rawNet > 0 ? '+' : ''}
                  {l.rawNet.toFixed(1)}
                </td>
                <td className="px-4 py-2.5 text-right font-mono font-bold text-primary-600 dark:text-primary-400">
                  {l.ctxNet > 0 ? '+' : ''}
                  {l.ctxNet.toFixed(1)}
                </td>
                <td className="px-4 py-2.5 text-right text-caption text-text-muted">{l.oppTier}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <Card variant="inset" className="mb-4">
        <p className="text-micro text-text-muted uppercase tracking-wider">Without Top Teammate</p>
        <p className="text-body text-text-secondary mt-1">
          Without{' '}
          <span className="text-primary-600 dark:text-primary-400 font-semibold">
            {player.lineupContext.withoutTopTeammate.teammate}
          </span>
          :
        </p>
        <p className="text-h2 font-mono font-bold tabular-nums text-text-primary mt-1">
          {player.lineupContext.withoutTopTeammate.netRtg > 0 ? '+' : ''}
          {player.lineupContext.withoutTopTeammate.netRtg.toFixed(1)} Net Rtg{' '}
          <span className="text-body text-text-muted">
            ({player.lineupContext.withoutTopTeammate.minutes} min)
          </span>
        </p>
      </Card>

      {/* Luck-Adjusted */}
      <SectionHeader title="Luck-Adjusted Metrics" />
      <div className="grid grid-cols-3 gap-3 mb-4">
        <Card variant="inset">
          <Stat
            label="Expected Wins"
            value={luck.xWins}
            hint={`Actual: ${luck.actualWins}`}
            size="md"
          />
        </Card>
        <Card variant="inset">
          <Stat label="Clutch EPA" value={luck.clutchEPA.toFixed(1)} size="md" />
        </Card>
        <Card variant="inset">
          <Stat label="Garbage Time Pts" value={`${luck.garbageTimePts.toFixed(1)}/g`} size="md" />
        </Card>
      </div>

      {/* Aggregate Impact Models */}
      <SectionHeader title="Aggregate Impact Models" />
      <Card>
        <ResponsiveContainer width="100%" height={250}>
          <BarChart data={impactModels} layout="vertical" margin={{ left: 60, right: 40 }}>
            <XAxis type="number" tick={{ fill: theme.axis, fontSize: 11 }} axisLine={{ stroke: theme.grid }} />
            <YAxis type="category" dataKey="name" tick={{ fill: theme.axis, fontSize: 12 }} axisLine={false} tickLine={false} />
            <Bar dataKey="value" radius={[0, 4, 4, 0]}>
              {impactModels.map((e, i) => (
                <Cell key={i} fill={e.value >= 0 ? theme.primary : theme.neg} />
              ))}
              <LabelList
                dataKey="value"
                position="right"
                formatter={(v: unknown) => Number(v).toFixed(1)}
                style={{ fill: theme.textPrimary, fontSize: 11 }}
              />
            </Bar>
          </BarChart>
        </ResponsiveContainer>
      </Card>
    </div>
  )
}

function DiffBar({ label, value, invert = false }: { label: string; value: number; invert?: boolean }) {
  const pct = Math.min(value / 1.3, 100)
  const isGood = invert ? value < 110 : value > 110
  const color = isGood ? 'bg-pos' : 'bg-neg'
  return (
    <div className="mb-2">
      <div className="flex justify-between text-caption mb-1">
        <span className="text-text-muted">{label}</span>
        <span className="font-mono tabular-nums text-text-primary">{value.toFixed(1)}</span>
      </div>
      <div className="w-full bg-surface-3 rounded-full h-2">
        <div className={`h-2 rounded-full ${color}`} style={{ width: `${pct}%` }} />
      </div>
    </div>
  )
}
