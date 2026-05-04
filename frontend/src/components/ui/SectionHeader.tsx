import type { ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface SectionHeaderProps {
  /** Required headline (rendered as `h3`). */
  title: string
  /** Optional uppercase tag rendered as a small pill next to the title. */
  tag?: string
  /** Optional secondary description rendered beneath the title. */
  description?: ReactNode
  /** Override the default vertical rhythm. */
  className?: string
}

/**
 * Standardized section header — replaces the bespoke
 * `text-sm uppercase tracking-[1.5px]` block in `cortex/shared.tsx`.
 * Keeps the rule-line affordance the cortex tabs rely on (a thin gray
 * divider extending to the right of the title) while routing colors
 * through the semantic surface tokens.
 *
 * Spacing rhythm:
 *   - Default block margin is `mt-12 mb-3` so consecutive sections breathe.
 *   - First-of-type sections collapse the top margin to keep the header
 *     flush with the page title (`first:mt-0`).
 */
export default function SectionHeader({
  title,
  tag,
  description,
  className,
}: SectionHeaderProps) {
  return (
    <div className={cn('mt-12 mb-3 first:mt-0', className)}>
      <div className="flex items-center gap-3">
        <h3 className="text-h3 font-semibold text-text-primary tracking-tight">
          {title}
        </h3>
        {tag ? (
          <span className="text-micro font-mono uppercase tracking-wider bg-primary-500/10 text-primary-600 dark:text-primary-400 px-2 py-0.5 rounded-full">
            {tag}
          </span>
        ) : null}
        <div className="flex-1 h-px bg-border-subtle" />
      </div>
      {description ? (
        <p className="mt-1 text-caption text-text-muted">{description}</p>
      ) : null}
    </div>
  )
}
