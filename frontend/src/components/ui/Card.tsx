import type { ElementType, ReactNode, ComponentPropsWithoutRef } from 'react'
import { cn } from '@/lib/utils'

export type CardVariant = 'panel' | 'inset' | 'bare'

interface CardOwnProps<E extends ElementType> {
  /** Visual treatment. `panel` (default) is a raised card; `inset` is a
   *  nested tile inside another panel; `bare` is structural-only spacing. */
  variant?: CardVariant
  /** Strip default padding for callers that need to manage their own
   *  internal layout (e.g. tables, charts that bleed to the edge). */
  padded?: boolean
  /** Polymorphic root element. Defaults to `div`. */
  as?: E
  className?: string
  children?: ReactNode
}

export type CardProps<E extends ElementType = 'div'> = CardOwnProps<E> &
  Omit<ComponentPropsWithoutRef<E>, keyof CardOwnProps<E>>

const VARIANT_BASE: Record<CardVariant, string> = {
  // panel = raised card. Light: white on gray-50 page; Dark: gray-900 on
  // gray-950 page. Surface tokens land us there with a cross-mode swap.
  panel: 'bg-surface dark:bg-surface-2 border border-border-subtle rounded-lg shadow-sm',
  // inset = nested tile inside a panel. Slightly darker in light (gray-50
  // already matches the original `bg-gray-50` callouts), and slightly lighter
  // than the panel in dark.
  inset: 'bg-surface-2 dark:bg-surface-3 border border-border-subtle rounded-md',
  bare: '',
}

const VARIANT_PADDING: Record<CardVariant, string> = {
  panel: 'p-4',
  inset: 'p-3',
  bare: '',
}

/**
 * Generic surface primitive used in place of the ad-hoc
 * `bg-white rounded-lg shadow-sm border border-gray-200 p-4` divs scattered
 * across the cortex tabs. Variants encode common nesting depths so the
 * surface palette stays consistent across light/dark.
 */
export default function Card<E extends ElementType = 'div'>({
  variant = 'panel',
  padded = true,
  as,
  className,
  children,
  ...rest
}: CardProps<E>) {
  const Component = (as ?? 'div') as ElementType
  return (
    <Component
      className={cn(
        VARIANT_BASE[variant],
        padded ? VARIANT_PADDING[variant] : '',
        className,
      )}
      {...rest}
    >
      {children}
    </Component>
  )
}
