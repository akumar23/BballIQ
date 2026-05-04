import SectionHeaderPrimitive from '@/components/ui/SectionHeader'

interface SectionHeaderProps {
  title: string
  tag?: string
}

/**
 * Backward-compatible wrapper around the new `ui/SectionHeader` primitive.
 * The shape is identical to the previous local implementation so the cortex
 * tabs that haven't been migrated yet continue to work without churn.
 */
export function SectionHeader({ title, tag }: SectionHeaderProps) {
  return <SectionHeaderPrimitive title={title} tag={tag} />
}

interface StatBoxProps {
  label: string
  value: string | number
  subtitle?: string
  diff?: number
  diffLabel?: string
  className?: string
}

export function StatBox({ label, value, subtitle, diff, diffLabel, className = '' }: StatBoxProps) {
  return (
    <div
      className={`bg-surface-3 border border-border-subtle rounded px-4 py-3 ${className}`}
    >
      <p className="text-micro text-text-muted uppercase tracking-wider">{label}</p>
      <p className="text-h3 font-mono font-bold tabular-nums text-text-primary mt-0.5">
        {value}
      </p>
      {subtitle && (
        <p className="text-micro text-text-muted font-mono mt-0.5">{subtitle}</p>
      )}
      {diff !== undefined && <DiffBadge value={diff} label={diffLabel} />}
    </div>
  )
}

interface DiffBadgeProps {
  value: number
  label?: string
}

export function DiffBadge({ value, label = 'vs LG' }: DiffBadgeProps) {
  const isPositive = value >= 0
  return (
    <span
      className={`inline-flex items-center gap-1 text-micro font-mono tabular-nums mt-1 px-1.5 py-0.5 rounded ${
        isPositive
          ? 'bg-pos-soft text-pos-strong dark:text-pos'
          : 'bg-neg-soft text-neg-strong dark:text-neg'
      }`}
    >
      {isPositive ? '+' : ''}
      {value.toFixed(1)} {label}
    </span>
  )
}

interface TagBadgeProps {
  text: string
}

export function TagBadge({ text }: TagBadgeProps) {
  return (
    <span className="text-[9px] font-mono uppercase tracking-wider bg-primary-500/10 text-primary-600 dark:text-primary-400 px-2 py-0.5 rounded-full">
      {text}
    </span>
  )
}

/**
 * Map raw PPP into a polarity color class. Mirrors `getPolarityClass` 5-bucket
 * ladder so the cortex tabs stay colorblind-safe and consistent.
 */
export function pppColor(ppp: number): string {
  if (ppp >= 1.15) return 'text-emerald-600 dark:text-emerald-400'
  if (ppp >= 1.05) return 'text-emerald-500 dark:text-emerald-300'
  if (ppp >= 0.95) return 'text-gray-700 dark:text-gray-300'
  if (ppp >= 0.85) return 'text-rose-500 dark:text-rose-300'
  return 'text-rose-600 dark:text-rose-400'
}

/**
 * Generic threshold-based color class for arbitrary metrics. Pass `invert`
 * for metrics where lower is better (turnovers, opp FG%).
 */
export function qualityColor(
  value: number,
  thresholds: { good: number; ok: number },
  options: { invert?: boolean } = {},
): string {
  const { invert = false } = options
  const isGood = invert ? value <= thresholds.good : value >= thresholds.good
  const isOk = invert ? value <= thresholds.ok : value >= thresholds.ok
  if (isGood) return 'text-emerald-600 dark:text-emerald-400'
  if (isOk) return 'text-gray-700 dark:text-gray-300'
  return 'text-rose-600 dark:text-rose-400'
}

/**
 * Background fill class for fit-score progress bars. The previous
 * implementation reused `bg-primary-600` for the "average" bucket which
 * collided with the brand color used for active/highlight states; replaced
 * with amber to give "average" its own slot in the polarity ladder.
 */
export function fitColor(score: number): string {
  if (score >= 90) return 'bg-emerald-500 dark:bg-emerald-400'
  if (score >= 75) return 'bg-emerald-400 dark:bg-emerald-300'
  if (score >= 60) return 'bg-amber-500 dark:bg-amber-400'
  if (score >= 40) return 'bg-rose-400 dark:bg-rose-300'
  return 'bg-rose-500 dark:bg-rose-400'
}

/**
 * Glyph paired with the color helpers above. Mirrors `getPolarityIcon` for
 * call sites that already use `pppColor`/`qualityColor`.
 */
export function polarityGlyph(
  percentile: number | null,
  options: { invert?: boolean } = {},
): string {
  if (percentile === null || Number.isNaN(percentile)) return '\u2022'
  const p = options.invert ? 100 - percentile : percentile
  if (p >= 80) return '\u25B2'
  if (p >= 60) return '\u25B4'
  if (p >= 40) return '\u2022'
  if (p >= 20) return '\u25BE'
  return '\u25BC'
}
