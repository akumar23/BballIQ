interface SectionHeaderProps {
  title: string
  tag?: string
}

export function SectionHeader({ title, tag }: SectionHeaderProps) {
  return (
    <div className="flex items-center gap-3 mb-4 mt-8 first:mt-0">
      <h3 className="text-sm uppercase tracking-[1.5px] text-gray-900 dark:text-white font-semibold">{title}</h3>
      {tag && <TagBadge text={tag} />}
      <div className="flex-1 h-px bg-gray-200 dark:bg-gray-700" />
    </div>
  )
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
    <div className={`bg-gray-50 border border-gray-200 rounded px-4 py-3 ${className}`}>
      <p className="text-[10px] text-gray-500 uppercase tracking-wider">{label}</p>
      <p className="text-xl font-mono font-bold text-gray-900 mt-0.5">{value}</p>
      {subtitle && <p className="text-[10px] text-gray-400 font-mono mt-0.5">{subtitle}</p>}
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
      className={`inline-flex items-center gap-1 text-[10px] font-mono mt-1 px-1.5 py-0.5 rounded ${
        isPositive ? 'bg-green-50 text-green-600' : 'bg-red-50 text-red-600'
      }`}
    >
      {isPositive ? '+' : ''}{value.toFixed(1)} {label}
    </span>
  )
}

interface TagBadgeProps {
  text: string
}

export function TagBadge({ text }: TagBadgeProps) {
  return (
    <span className="text-[9px] font-mono uppercase tracking-wider bg-primary-500/10 text-primary-600 px-2 py-0.5 rounded-full">
      {text}
    </span>
  )
}

export function pppColor(ppp: number): string {
  if (ppp >= 1.05) return 'text-green-600'
  if (ppp >= 0.95) return 'text-yellow-600'
  return 'text-red-600'
}

export function qualityColor(value: number, thresholds: { good: number; ok: number }): string {
  if (value >= thresholds.good) return 'text-green-600'
  if (value >= thresholds.ok) return 'text-yellow-600'
  return 'text-red-600'
}

export function fitColor(score: number): string {
  if (score >= 90) return 'bg-green-500'
  if (score >= 75) return 'bg-yellow-500'
  if (score >= 60) return 'bg-primary-600'
  return 'bg-red-500'
}
