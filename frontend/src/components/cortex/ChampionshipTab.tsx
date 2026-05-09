import type { CortexPlayer } from '@/data/cortexTypes'
import Card from '@/components/ui/Card'
import SectionHeader from '@/components/ui/SectionHeader'
import Stat from '@/components/ui/Stat'
import { fitColor } from './shared'

export default function ChampionshipTab({ player }: { player: CortexPlayer }) {
  const c = player.championship

  return (
    <div>
      {/* Championship Index Hero */}
      <SectionHeader title="Championship Index" tag="RING PROBABILITY" />
      <Card padded={false} className="p-6 mb-4">
        <div className="flex flex-col lg:flex-row items-center gap-8">
          <svg width="180" height="180" viewBox="0 0 180 180">
            <circle
              cx="90"
              cy="90"
              r="74"
              fill="none"
              style={{ stroke: 'rgb(var(--color-border-subtle))' }}
              strokeWidth="10"
            />
            <circle
              cx="90"
              cy="90"
              r="74"
              fill="none"
              stroke="#2563eb"
              strokeWidth="10"
              strokeDasharray={`${(c.index / 100) * 465} 465`}
              strokeLinecap="round"
              transform="rotate(-90 90 90)"
            />
            <text
              x="90"
              y="82"
              textAnchor="middle"
              className="fill-text-primary text-4xl font-mono font-bold"
            >
              {c.index}
            </text>
            <text
              x="90"
              y="105"
              textAnchor="middle"
              className="fill-text-muted text-[10px] font-mono"
            >
              /100
            </text>
          </svg>
          <div className="flex-1">
            <p className="text-caption font-mono text-primary-600 dark:text-primary-400 tracking-widest mb-2">
              {c.tier}
            </p>
            <p className="text-body text-text-secondary leading-relaxed">{c.verdict}</p>
          </div>
        </div>
        <div className="grid grid-cols-1 sm:grid-cols-3 gap-3 mt-6">
          <Card variant="inset">
            <Stat label="Win Prob / Season" value={`${c.winProbability}%`} size="md" />
          </Card>
          <Card variant="inset">
            <Stat
              label="Historical Base Rate"
              value={`${c.historicalBaseRate}%`}
              hint="any #1 option"
              size="md"
            />
          </Card>
          <Card variant="inset">
            <Stat label="Multiplier vs Base" value={`${c.multiplier}x`} size="md" />
          </Card>
        </div>
      </Card>

      {/* Championship Pillars */}
      <SectionHeader title="Championship Pillars" />
      <div className="space-y-2 mb-4">
        {c.pillars.map((p) => (
          <Card key={p.name}>
            <div className="flex items-center gap-4 mb-2">
              <div className="w-52 shrink-0">
                <p className="text-body text-text-primary">{p.name}</p>
              </div>
              <div className="w-12 shrink-0 text-right">
                <span className="font-mono tabular-nums font-bold text-text-primary">{p.score}</span>
              </div>
              <div className="w-12 shrink-0 text-right">
                <span className="text-micro font-mono tabular-nums text-text-muted">{p.weight}%</span>
              </div>
              <div className="flex-1">
                <div className="w-full bg-surface-3 rounded-full h-2">
                  <div
                    className={`h-2 rounded-full ${fitColor(p.score)}`}
                    style={{ width: `${p.score}%` }}
                  />
                </div>
              </div>
            </div>
            <p className="text-micro text-text-muted ml-64">{p.explanation}</p>
          </Card>
        ))}
      </div>

      {/* Playoff Projection */}
      <SectionHeader title="Playoff Performance Projection" />
      <Card className="mb-4">
        <div className="grid grid-cols-2 sm:grid-cols-4 gap-3 mb-4">
          {[
            { label: 'PPG', proj: c.playoffProjection.ppg, drop: c.playoffProjection.regToPlayoffDrop.ppg },
            { label: 'TS%', proj: c.playoffProjection.ts, drop: c.playoffProjection.regToPlayoffDrop.ts },
            { label: 'AST', proj: c.playoffProjection.ast, drop: c.playoffProjection.regToPlayoffDrop.ast },
            { label: 'DRtg', proj: c.playoffProjection.drtg, drop: c.playoffProjection.regToPlayoffDrop.drtg },
          ].map((s) => (
            <div key={s.label} className="text-center">
              <p className="text-micro text-text-muted uppercase tracking-wider">{s.label}</p>
              <p className="text-h2 font-mono font-bold tabular-nums text-text-primary mt-1">
                {s.label === 'TS%' ? (s.proj * 100).toFixed(1) : s.proj.toFixed(1)}
              </p>
              <p
                className={`text-micro font-mono tabular-nums mt-1 ${
                  s.drop <= 0
                    ? 'text-neg-strong dark:text-neg'
                    : s.label === 'DRtg'
                      ? 'text-neg-strong dark:text-neg'
                      : 'text-pos-strong dark:text-pos'
                }`}
              >
                {s.label === 'TS%'
                  ? (s.drop * 100).toFixed(1)
                  : s.drop > 0
                    ? `+${s.drop.toFixed(1)}`
                    : s.drop.toFixed(1)}{' '}
                reg→playoff
              </p>
            </div>
          ))}
        </div>
        <p className="text-micro text-text-muted">{c.playoffProjection.comparisonNote}</p>
      </Card>

      {/* Supporting Cast */}
      <SectionHeader title="Supporting Cast Requirements" />
      <div className="grid grid-cols-2 lg:grid-cols-4 gap-3 mb-2">
        <Card variant="inset">
          <Stat label="Min 2nd Option" value={c.supportingCast.min2ndOption} size="md" />
        </Card>
        <Card variant="inset">
          <Stat label="Spacing Need" value={c.supportingCast.spacingNeed} size="md" />
        </Card>
        <Card variant="inset">
          <Stat label="Defensive Need" value={c.supportingCast.defensiveNeed} size="md" />
        </Card>
        <Card variant="inset">
          <Stat label="Cap Flexibility" value={c.supportingCast.capFlexibility} size="md" />
        </Card>
      </div>
      <Card className="bg-primary-50 dark:bg-primary-500/10 border-primary-200 dark:border-primary-500/30 mb-4">
        <p className="text-micro text-primary-600 dark:text-primary-400 uppercase tracking-wider mb-1">
          Blueprint
        </p>
        <p className="text-body text-text-secondary">{c.supportingCast.blueprint}</p>
      </Card>

      {/* Comparables */}
      <SectionHeader title="Championship Run Comparables" />
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-3">
        {c.comparables.map((comp) => (
          <Card key={`${comp.player}-${comp.year}`}>
            <div className="flex justify-between items-start mb-2">
              <div>
                <p className="text-body text-text-primary font-semibold">
                  {comp.player} ({comp.year})
                </p>
                <p className="text-micro text-text-muted">{comp.role}</p>
              </div>
              <span className="text-h3" aria-hidden="true">
                {comp.won ? '🏆' : '✗'}
              </span>
            </div>
            <div className="flex gap-4 text-caption font-mono tabular-nums text-text-muted mb-2">
              <span>Cast: {comp.castStrength}</span>
              <span>Index: {comp.championshipIndex}</span>
            </div>
            <p className="text-micro text-text-muted">{comp.analysis}</p>
          </Card>
        ))}
      </div>
    </div>
  )
}
