import {
  useEffect,
  useId,
  useMemo,
  useRef,
  useState,
  type KeyboardEvent,
  type ReactNode,
} from 'react'
import { cn } from '@/lib/utils'

export interface ComboboxOption<T> {
  /** Stable identifier used as React key + selected value. */
  value: string
  /** Visible label rendered into the option button. */
  label: string
  /** Optional secondary text shown after the label. */
  hint?: string
  /** Original payload — passed through to onChange. */
  data: T
}

interface ComboboxProps<T> {
  /** All available options. Filtering is performed locally. */
  options: ComboboxOption<T>[]
  /** Currently selected value (controlled). */
  value: string
  /** Fires with the new value when the user picks an option. */
  onChange: (value: string, option: ComboboxOption<T>) => void
  /** Placeholder shown when the input is empty and unfocused. */
  placeholder?: string
  /** Visually hidden label associated with the input via aria-labelledby. */
  ariaLabel: string
  /** Optional extra description text rendered under the input. */
  description?: ReactNode
  /** Fires when no options match the current query (e.g. for empty state copy). */
  emptyMessage?: string
  /** Disables interaction. */
  disabled?: boolean
  /** Optional id forwarded to the underlying input (deep-link/test hooks). */
  inputId?: string
  /** Forwarded class for the wrapping element. */
  className?: string
}

/**
 * Minimal accessible combobox following the WAI-ARIA 1.2 combobox pattern
 * (single-select, manual selection). No external deps — pure React + Tailwind.
 *
 * Keyboard:
 *   ArrowDown / ArrowUp  — move highlight (wraps).
 *   Home / End           — jump to first / last.
 *   Enter                — select highlighted option.
 *   Escape               — close popup, restore selected label.
 *   Tab                  — close popup, keep current selection.
 */
export default function Combobox<T>({
  options,
  value,
  onChange,
  placeholder = 'Select…',
  ariaLabel,
  description,
  emptyMessage = 'No matches',
  disabled = false,
  inputId,
  className,
}: ComboboxProps<T>) {
  const reactId = useId()
  const listboxId = `${reactId}-listbox`
  const labelId = `${reactId}-label`
  const generatedInputId = inputId ?? `${reactId}-input`

  const inputRef = useRef<HTMLInputElement>(null)
  const containerRef = useRef<HTMLDivElement>(null)
  const optionRefs = useRef<Record<number, HTMLLIElement | null>>({})

  const [open, setOpen] = useState(false)
  const [query, setQuery] = useState('')
  const [highlight, setHighlight] = useState(0)

  const selectedOption = useMemo(
    () => options.find((o) => o.value === value) ?? null,
    [options, value],
  )

  // Filtered list — case-insensitive substring match on the visible label.
  const filtered = useMemo(() => {
    if (!query.trim()) return options
    const q = query.toLowerCase()
    return options.filter(
      (o) =>
        o.label.toLowerCase().includes(q) ||
        (o.hint?.toLowerCase().includes(q) ?? false),
    )
  }, [options, query])

  // Sync displayed query with the selected option whenever the popup is closed.
  useEffect(() => {
    if (!open) {
      setQuery(selectedOption?.label ?? '')
    }
  }, [open, selectedOption])

  // Keep highlight in range as the filtered list shrinks/grows.
  useEffect(() => {
    if (highlight >= filtered.length) {
      setHighlight(filtered.length === 0 ? 0 : filtered.length - 1)
    }
  }, [filtered.length, highlight])

  // Scroll the active option into view as the user navigates.
  useEffect(() => {
    if (!open) return
    const node = optionRefs.current[highlight]
    if (node) node.scrollIntoView({ block: 'nearest' })
  }, [open, highlight])

  // Click-outside to dismiss.
  useEffect(() => {
    if (!open) return
    const onDocMouseDown = (e: MouseEvent) => {
      if (!containerRef.current) return
      if (!containerRef.current.contains(e.target as Node)) {
        setOpen(false)
      }
    }
    document.addEventListener('mousedown', onDocMouseDown)
    return () => document.removeEventListener('mousedown', onDocMouseDown)
  }, [open])

  const commit = (idx: number) => {
    const opt = filtered[idx]
    if (!opt) return
    onChange(opt.value, opt)
    setOpen(false)
    setQuery(opt.label)
    inputRef.current?.blur()
  }

  const handleKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (disabled) return
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        if (!open) {
          setOpen(true)
          return
        }
        setHighlight((h) => (filtered.length === 0 ? 0 : (h + 1) % filtered.length))
        return
      case 'ArrowUp':
        e.preventDefault()
        if (!open) {
          setOpen(true)
          return
        }
        setHighlight((h) =>
          filtered.length === 0 ? 0 : (h - 1 + filtered.length) % filtered.length,
        )
        return
      case 'Home':
        if (!open) return
        e.preventDefault()
        setHighlight(0)
        return
      case 'End':
        if (!open) return
        e.preventDefault()
        setHighlight(Math.max(0, filtered.length - 1))
        return
      case 'Enter':
        if (!open) return
        e.preventDefault()
        commit(highlight)
        return
      case 'Escape':
        if (!open) return
        e.preventDefault()
        setOpen(false)
        setQuery(selectedOption?.label ?? '')
        return
      case 'Tab':
        setOpen(false)
        return
      default:
        return
    }
  }

  return (
    <div ref={containerRef} className={cn('relative', className)}>
      <span id={labelId} className="sr-only">
        {ariaLabel}
      </span>
      <input
        ref={inputRef}
        id={generatedInputId}
        type="text"
        role="combobox"
        autoComplete="off"
        aria-labelledby={labelId}
        aria-expanded={open}
        aria-controls={listboxId}
        aria-autocomplete="list"
        aria-activedescendant={
          open && filtered[highlight] ? `${listboxId}-opt-${highlight}` : undefined
        }
        disabled={disabled}
        placeholder={placeholder}
        value={query}
        onChange={(e) => {
          setQuery(e.target.value)
          if (!open) setOpen(true)
          setHighlight(0)
        }}
        onFocus={() => {
          if (!disabled) setOpen(true)
        }}
        onKeyDown={handleKeyDown}
        className="w-full px-3 py-2 bg-white dark:bg-gray-800 border border-gray-200 dark:border-gray-700 rounded text-sm text-gray-900 dark:text-gray-100 font-mono placeholder:text-gray-400 dark:placeholder:text-gray-500 focus:outline-none focus-visible:ring-2 focus-visible:ring-primary-500 focus:border-primary-500 disabled:cursor-not-allowed disabled:opacity-60"
      />

      {open && (
        <ul
          id={listboxId}
          role="listbox"
          aria-labelledby={labelId}
          className="absolute z-40 mt-1 w-full max-h-72 overflow-y-auto rounded-md border border-gray-200 dark:border-gray-700 bg-white dark:bg-gray-900 shadow-lg ring-1 ring-black/5"
        >
          {filtered.length === 0 ? (
            <li
              role="option"
              aria-selected="false"
              aria-disabled="true"
              className="px-3 py-2 text-sm text-gray-500 dark:text-gray-400 font-mono"
            >
              {emptyMessage}
            </li>
          ) : (
            filtered.map((opt, idx) => {
              const isHighlighted = idx === highlight
              const isSelected = opt.value === value
              return (
                <li
                  key={opt.value}
                  id={`${listboxId}-opt-${idx}`}
                  ref={(el) => {
                    optionRefs.current[idx] = el
                  }}
                  role="option"
                  aria-selected={isSelected}
                  className={cn(
                    'px-3 py-2 text-sm cursor-pointer font-mono flex justify-between items-center gap-3',
                    isHighlighted
                      ? 'bg-primary-50 dark:bg-primary-500/10 text-primary-700 dark:text-primary-300'
                      : 'text-gray-800 dark:text-gray-200',
                    isSelected && !isHighlighted && 'font-semibold',
                  )}
                  onMouseDown={(e) => {
                    // mousedown so click-outside doesn't fire before commit.
                    e.preventDefault()
                    commit(idx)
                  }}
                  onMouseEnter={() => setHighlight(idx)}
                >
                  <span className="truncate">{opt.label}</span>
                  {opt.hint && (
                    <span className="shrink-0 text-xs text-gray-500 dark:text-gray-400">
                      {opt.hint}
                    </span>
                  )}
                </li>
              )
            })
          )}
        </ul>
      )}

      {description && (
        <p className="mt-1 text-xs text-gray-500 dark:text-gray-400 font-mono">{description}</p>
      )}
    </div>
  )
}
