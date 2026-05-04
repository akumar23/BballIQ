import type { ReactNode, TableHTMLAttributes } from 'react'
import { cn } from '@/lib/utils'

export interface DataTableProps extends TableHTMLAttributes<HTMLTableElement> {
  /** `<caption>` content for screen readers. Required for a11y; pass an
   *  `sr-only` string when the table doesn't need a visible caption. */
  caption?: ReactNode
  /** When `false`, drops zebra striping. Defaults to `true`. */
  striped?: boolean
  /** When `false`, drops the sticky `<thead>` (e.g. for tiny tables). */
  stickyHeader?: boolean
  children: ReactNode
}

/**
 * Pure styling shell for the leaderboard-style tables across cortex tabs +
 * leaderboard pages. Sort/header logic stays in callers (using the existing
 * `SortArrow` pattern from `GameLogsTab`) — this component only owns the
 * presentation: sticky header, zebra striping, tabular numerics, and the
 * outer scroll container.
 *
 * Convention: numeric columns should add `text-right` + `font-mono` on their
 * `<td>`; the wrapper applies `tabular-nums` globally so digits align across
 * rows without per-cell repetition.
 */
export default function DataTable({
  caption,
  striped = true,
  stickyHeader = true,
  className,
  children,
  ...rest
}: DataTableProps) {
  return (
    <div className="bg-surface dark:bg-surface-2 border border-border-subtle rounded-lg shadow-sm overflow-hidden">
      <div className="overflow-x-auto">
        <table
          className={cn(
            'w-full text-body tabular-nums',
            // Sticky header — renders the thead row above scrolling tbody.
            stickyHeader &&
              '[&_thead]:sticky [&_thead]:top-0 [&_thead]:z-10 [&_thead]:bg-surface-2 [&_thead]:dark:bg-surface-3',
            // Zebra striping — odd-row tint pulled from surface-3 so the
            // contrast scales with the active theme.
            striped &&
              '[&_tbody_tr:nth-child(odd)]:bg-surface-3/40 [&_tbody_tr:nth-child(odd)]:dark:bg-surface-3/30',
            // Hover affordance.
            '[&_tbody_tr:hover]:bg-surface-3/70 [&_tbody_tr:hover]:dark:bg-surface-3/60',
            // Subtle row dividers.
            '[&_tbody_tr]:border-b [&_tbody_tr]:border-border-subtle/60',
            '[&_tbody_tr:last-child]:border-b-0',
            className,
          )}
          {...rest}
        >
          {caption ? <caption className="sr-only">{caption}</caption> : null}
          {children}
        </table>
      </div>
    </div>
  )
}
