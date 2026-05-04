import { clsx, type ClassValue } from 'clsx'
import { twMerge } from 'tailwind-merge'

export function cn(...inputs: ClassValue[]) {
  return twMerge(clsx(inputs))
}

export function formatMetric(value: number | null): string {
  if (value === null) return '-'
  return Number(value).toFixed(1)
}

/**
 * Polarity classes — colorblind-safe ordered ladder using 5 buckets.
 * Pair with `getPolarityIcon` in the same call site for redundant encoding.
 *
 * Buckets (default polarity, higher = better):
 *   >= 80 strong-positive | >= 60 positive | 40-59 neutral | >= 20 negative | else strong-negative
 *
 * Pass `invert: true` for metrics where lower values are better (e.g. defense
 * DRtg, opponent FG%, turnovers). The helper just mirrors the percentile.
 */
export function getPolarityClass(
  percentile: number | null,
  options: { invert?: boolean } = {},
): string {
  if (percentile === null || Number.isNaN(percentile)) {
    return 'text-gray-500 dark:text-gray-400'
  }
  const p = options.invert ? 100 - percentile : percentile
  if (p >= 80) return 'text-emerald-600 dark:text-emerald-400'
  if (p >= 60) return 'text-emerald-500 dark:text-emerald-300'
  if (p >= 40) return 'text-gray-700 dark:text-gray-300'
  if (p >= 20) return 'text-rose-500 dark:text-rose-300'
  return 'text-rose-600 dark:text-rose-400'
}

/**
 * Glyph paired with `getPolarityClass` so colorblind users still get the
 * directional cue. Returns a single character suitable for inline rendering
 * next to a number.
 */
export function getPolarityIcon(
  percentile: number | null,
  options: { invert?: boolean } = {},
): string {
  if (percentile === null || Number.isNaN(percentile)) return '•'
  const p = options.invert ? 100 - percentile : percentile
  if (p >= 80) return '\u25B2' // ▲
  if (p >= 60) return '\u25B4' // ▴
  if (p >= 40) return '\u2022' // •
  if (p >= 20) return '\u25BE' // ▾
  return '\u25BC' // ▼
}

/**
 * @deprecated Use `getPolarityClass` instead. Kept as a thin shim so any
 * stragglers continue to compile while we sweep the codebase.
 */
export function getPercentileColor(percentile: number | null): string {
  return getPolarityClass(percentile)
}
