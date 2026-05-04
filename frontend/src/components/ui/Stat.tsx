import type { ReactNode } from 'react'
import { cn, getPolarityClass, getPolarityIcon } from '@/lib/utils'

export type StatSize = 'sm' | 'md' | 'lg'
export type StatAlign = 'left' | 'center'

export interface StatProps {
  /** Short uppercase label rendered above the value. */
  label: string
  /** Pre-formatted value — caller controls precision/units. */
  value: ReactNode
  /** Optional 0–100 percentile. When provided, applies the polarity color
   *  and prepends the directional glyph for colorblind redundancy. */
  polarity?: number | null
  /** Set to `true` if the metric is "lower is better" (DRtg, opp FG%, TOV). */
  invertPolarity?: boolean
  /** Type-ramp slot for the value. `md` (default) maps to `text-h3`. */
  size?: StatSize
  /** Optional caption below the label. */
  hint?: ReactNode
  /** Horizontal alignment. Defaults to `left`. */
  align?: StatAlign
  className?: string
}

const SIZE_CLASS: Record<StatSize, string> = {
  sm: 'text-body',
  md: 'text-h3',
  lg: 'text-h2',
}

/**
 * Single-value stat tile. Consolidates the StatBox in cortex/shared.tsx, the
 * sticky-header KPIs on the Player Card page, and the bespoke tiles on
 * PlayerDetailPage. Numeric values inherit `tabular-nums` so columns of
 * stats line up without ad-hoc font-mono callouts.
 */
export default function Stat({
  label,
  value,
  polarity,
  invertPolarity,
  size = 'md',
  hint,
  align = 'left',
  className,
}: StatProps) {
  const hasPolarity = polarity !== undefined && polarity !== null
  const polarityClass = hasPolarity
    ? getPolarityClass(polarity, { invert: invertPolarity })
    : 'text-text-primary'
  const glyph = hasPolarity ? getPolarityIcon(polarity, { invert: invertPolarity }) : null

  return (
    <div className={cn(align === 'center' ? 'text-center' : 'text-left', className)}>
      <p className="text-micro text-text-muted uppercase tracking-wider">{label}</p>
      {hint ? (
        <p className="text-micro text-text-muted mt-0.5">{hint}</p>
      ) : null}
      <p
        className={cn(
          'mt-1 font-mono font-bold tabular-nums inline-flex items-center gap-1',
          SIZE_CLASS[size],
          polarityClass,
        )}
      >
        {glyph ? (
          <span aria-hidden="true" className="text-[0.85em]">
            {glyph}
          </span>
        ) : null}
        <span>{value}</span>
      </p>
    </div>
  )
}
