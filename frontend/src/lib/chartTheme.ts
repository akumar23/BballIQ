/**
 * Centralized Recharts theming. Reads CSS variables (defined in
 * `styles/index.css` under `:root` / `.dark`) at runtime so the same code
 * paths produce light or dark colors automatically.
 *
 * Recharts writes these values into SVG attributes (`stroke`, `fill`),
 * which do NOT resolve `var()` expressions. We therefore resolve the
 * variable to a literal `rgb(r g b)` string here — call this from inside
 * the component body so it re-evaluates on each render. A theme toggle
 * triggers a parent re-render via the layout's state update, so charts
 * pick up the new palette on the next paint.
 */

interface ChartTheme {
  grid: string
  axis: string
  axisLine: string
  tooltipBg: string
  tooltipBorder: string
  textPrimary: string
  textMuted: string
  pos: string
  neg: string
  warn: string
  primary: string
}

/** Sensible light-mode fallbacks for SSR / pre-hydration paths. */
const FALLBACK: Record<string, string> = {
  '--color-chart-grid': '229 231 235',
  '--color-chart-axis': '107 114 128',
  '--color-chart-tooltip-bg': '255 255 255',
  '--color-chart-tooltip-border': '229 231 235',
  '--color-text-primary': '17 24 39',
  '--color-text-muted': '107 114 128',
  '--color-pos': '16 185 129',
  '--color-neg': '244 63 94',
  '--color-warn': '245 158 11',
}

function readVar(name: string): string {
  if (typeof window === 'undefined' || typeof document === 'undefined') {
    return `rgb(${FALLBACK[name] ?? '0 0 0'})`
  }
  const raw = getComputedStyle(document.documentElement)
    .getPropertyValue(name)
    .trim()
  const triplet = raw.length > 0 ? raw : (FALLBACK[name] ?? '0 0 0')
  return `rgb(${triplet})`
}

/** Returns the live chart theme. Always invoke from inside a component (not
 *  at module scope) so it reflects the currently-applied theme. */
export function getChartTheme(): ChartTheme {
  return {
    grid: readVar('--color-chart-grid'),
    axis: readVar('--color-chart-axis'),
    axisLine: readVar('--color-chart-grid'),
    tooltipBg: readVar('--color-chart-tooltip-bg'),
    tooltipBorder: readVar('--color-chart-tooltip-border'),
    textPrimary: readVar('--color-text-primary'),
    textMuted: readVar('--color-text-muted'),
    pos: readVar('--color-pos'),
    neg: readVar('--color-neg'),
    warn: readVar('--color-warn'),
    // Brand primary is intentionally a literal blue across themes. If we
    // ever theme it, switch to `readVar('--color-primary')`.
    primary: '#2563eb',
  }
}

/** Convenience presets for the most common Recharts props so call sites stay
 *  terse. Always invoke from inside the component body. */
export function getChartProps() {
  const t = getChartTheme()
  return {
    grid: { stroke: t.grid, strokeDasharray: '3 3' as const },
    axisTick: { fill: t.axis, fontSize: 11 },
    axisLine: { stroke: t.axisLine },
    tooltipContentStyle: {
      backgroundColor: t.tooltipBg,
      border: `1px solid ${t.tooltipBorder}`,
      borderRadius: 8,
      fontSize: 12,
      color: t.textPrimary,
    },
    tooltipLabelStyle: { color: t.textPrimary },
    tooltipItemStyle: { color: t.textPrimary },
    legendStyle: { fontSize: 12, color: t.textMuted },
  }
}
