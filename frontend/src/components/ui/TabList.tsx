import { useId, type KeyboardEvent, type ReactNode } from 'react'
import { cn } from '@/lib/utils'

export interface TabItem<K extends string> {
  /** Stable key matching the active tab state. */
  key: K
  /** Visible label rendered inside the tab. */
  label: ReactNode
  /** Optional native title/description. */
  title?: string
}

interface TabListProps<K extends string> {
  tabs: TabItem<K>[]
  activeKey: K
  onChange: (key: K) => void
  /** Required for screen readers — describes the section the tabs control. */
  ariaLabel: string
  /** Optional id linking back to the panel (consumer wires this on the body). */
  panelId?: string
  /** Optional class merged onto the outer wrapper. */
  className?: string
  /** Variant lets call sites pick between full pill style and compact strip. */
  variant?: 'pill' | 'underline'
}

/**
 * Tiny accessible tablist that implements the WAI-ARIA tab pattern with
 * roving tabindex + arrow-key navigation. Intentionally compact — call sites
 * handle the panel rendering themselves so this stays generic.
 */
export default function TabList<K extends string>({
  tabs,
  activeKey,
  onChange,
  ariaLabel,
  panelId,
  className,
  variant = 'pill',
}: TabListProps<K>) {
  const idBase = useId()

  const handleKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const idx = tabs.findIndex((t) => t.key === activeKey)
    if (idx < 0) return
    let nextIdx: number | null = null
    if (e.key === 'ArrowRight') nextIdx = (idx + 1) % tabs.length
    else if (e.key === 'ArrowLeft') nextIdx = (idx - 1 + tabs.length) % tabs.length
    else if (e.key === 'Home') nextIdx = 0
    else if (e.key === 'End') nextIdx = tabs.length - 1
    if (nextIdx === null) return
    e.preventDefault()
    const nextKey = tabs[nextIdx].key
    onChange(nextKey)
    // Move focus to the new tab so screen readers announce it. Defer to the
    // next frame so React has flushed the new tabIndex/aria-selected state
    // before we steal focus.
    const tabId = `${idBase}-tab-${nextKey}`
    requestAnimationFrame(() => {
      document.getElementById(tabId)?.focus()
    })
  }

  return (
    <div
      role="tablist"
      aria-label={ariaLabel}
      onKeyDown={handleKeyDown}
      className={cn('flex flex-wrap gap-2', className)}
    >
      {tabs.map((tab) => {
        const isActive = tab.key === activeKey
        const tabId = `${idBase}-tab-${tab.key}`
        const baseClass =
          variant === 'underline'
            ? cn(
                'px-4 py-2.5 text-xs uppercase tracking-[1.5px] transition-all rounded-t border-b-2',
                isActive
                  ? 'text-primary-600 dark:text-primary-400 border-primary-600 dark:border-primary-400'
                  : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white border-transparent',
              )
            : cn(
                'px-4 py-2 rounded-lg font-medium transition-colors',
                isActive
                  ? 'bg-primary-600 text-white dark:bg-primary-700'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200 dark:bg-gray-800 dark:text-gray-200 dark:hover:bg-gray-700',
              )
        return (
          <button
            key={tab.key}
            id={tabId}
            type="button"
            role="tab"
            aria-selected={isActive}
            aria-controls={panelId}
            tabIndex={isActive ? 0 : -1}
            title={tab.title}
            onClick={() => onChange(tab.key)}
            className={baseClass}
          >
            {tab.label}
          </button>
        )
      })}
    </div>
  )
}
