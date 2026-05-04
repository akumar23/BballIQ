import {
  forwardRef,
  useCallback,
  useEffect,
  useId,
  useImperativeHandle,
  useLayoutEffect,
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
  /** Visible label (used for substring matching and as default render text). */
  label: string
  /** Optional secondary keyword text — also matched by the filter. */
  hint?: string
  /** Original payload — passed through to onChange and render props. */
  data: T
}

/** Imperative handle exposed through `ref` so parents can focus / open the picker. */
export interface ComboboxHandle {
  /** Move keyboard focus to the trigger button. */
  focus: () => void
  /** Open the popover and focus the search input. */
  open: () => void
  /** Close the popover (and return focus to the trigger). */
  close: () => void
}

interface ComboboxProps<T> {
  /** All available options. Filtering is performed locally. */
  options: ComboboxOption<T>[]
  /** Currently selected value (controlled). */
  value: string
  /** Fires with the new value when the user picks an option. */
  onChange: (value: string, option: ComboboxOption<T>) => void
  /** Visually-hidden label associated with the combobox via aria-labelledby. */
  ariaLabel: string
  /** Placeholder shown inside the search input. */
  searchPlaceholder?: string
  /** Placeholder for the trigger button when no option is selected. */
  triggerPlaceholder?: string
  /** Optional extra description text rendered under the trigger. */
  description?: ReactNode
  /** Copy shown when filter yields no matches. Receives the active query. */
  emptyMessage?: (query: string) => ReactNode
  /** Disables interaction. */
  disabled?: boolean
  /** Optional id forwarded to the underlying trigger (test/deeplink hooks). */
  triggerId?: string
  /** Forwarded class for the wrapping element. */
  className?: string
  /**
   * Custom trigger renderer. When provided, the rendered node is wrapped in a
   * button so the consumer doesn't have to wire ARIA / keyboard handlers.
   * Receives the currently selected option (may be null if nothing matches).
   */
  renderTrigger?: (selected: ComboboxOption<T> | null) => ReactNode
  /**
   * Custom option renderer. Receives the option, query, and selected/active
   * flags so the consumer can highlight matched substrings, render avatars,
   * etc. When omitted the default label/hint layout is used.
   */
  renderOption?: (
    option: ComboboxOption<T>,
    state: { query: string; isActive: boolean; isSelected: boolean },
  ) => ReactNode
}

/**
 * Score how well an option matches the given query. Higher is better, 0 means
 * "no match — exclude". The scoring is intentionally simple but covers the
 * cases users actually expect:
 *
 *   - exact label match               -> 1000
 *   - label starts with query         ->  500 + length bonus
 *   - hint starts with query          ->  400
 *   - all query words appear in label ->  200 + position bonus
 *   - subsequence match (fuzzy)       ->  100 + density bonus
 *
 * Returning a numeric score (rather than a boolean) lets us sort the filtered
 * list so the most relevant matches sit at the top of the listbox.
 */
function scoreMatch(option: { label: string; hint?: string }, query: string): number {
  if (!query) return 1
  const haystack = option.label.toLowerCase()
  const hint = (option.hint ?? '').toLowerCase()
  const needle = query.toLowerCase().trim()
  if (!needle) return 1

  if (haystack === needle) return 1000
  if (haystack.startsWith(needle)) return 500 + needle.length
  if (hint.startsWith(needle)) return 400 + needle.length

  // Multi-word: every whitespace-delimited token must hit somewhere in the
  // haystack (or hint) for the option to match. This is what makes "lebron lal"
  // resolve correctly even though the substring "lebron lal" never appears.
  const tokens = needle.split(/\s+/).filter(Boolean)
  if (tokens.length > 1) {
    const allInLabel = tokens.every((t) => haystack.includes(t))
    if (allInLabel) {
      const firstIdx = haystack.indexOf(tokens[0])
      return 250 - Math.min(firstIdx, 200)
    }
    const allAcross = tokens.every((t) => haystack.includes(t) || hint.includes(t))
    if (allAcross) return 200
  } else if (haystack.includes(needle)) {
    const idx = haystack.indexOf(needle)
    return 300 - Math.min(idx, 200)
  } else if (hint.includes(needle)) {
    return 180
  }

  // Fuzzy subsequence: every char of the needle must appear in the haystack
  // in order (skipping is allowed). Density bonus rewards tighter matches.
  let hi = 0
  let firstHit = -1
  let lastHit = -1
  for (let qi = 0; qi < needle.length; qi++) {
    const ch = needle[qi]
    const found = haystack.indexOf(ch, hi)
    if (found < 0) return 0
    if (firstHit < 0) firstHit = found
    lastHit = found
    hi = found + 1
  }
  const span = Math.max(1, lastHit - firstHit + 1)
  const density = Math.round((needle.length / span) * 80)
  return 100 + density
}

/**
 * Trigger-button + popover-with-search combobox following the WAI-ARIA 1.2
 * combobox pattern (`aria-haspopup="listbox"`).
 *
 * Why a popover instead of an inline editable input?
 *   - The trigger surfaces the *current* selection at a glance (we render the
 *     player's avatar, team, season — not a stale text label).
 *   - The search input always starts empty, so opening the popover never
 *     filters away every option but the current one.
 *   - On mobile the popover transparently upgrades to a full-width bottom
 *     sheet with ≥44px touch targets, instead of a tiny dropdown.
 *
 * Keyboard:
 *   Trigger:           Enter / Space / ArrowDown — open popover
 *   Search input:      ArrowDown/ArrowUp move highlight (wraps);
 *                      Home/End jump; Enter commits; Esc closes; Tab closes.
 *   Selection commit:  closes popover and returns focus to the trigger.
 */
function ComboboxInner<T>(
  {
    options,
    value,
    onChange,
    ariaLabel,
    searchPlaceholder = 'Type to search…',
    triggerPlaceholder = 'Select…',
    description,
    emptyMessage,
    disabled = false,
    triggerId,
    className,
    renderTrigger,
    renderOption,
  }: ComboboxProps<T>,
  ref: React.Ref<ComboboxHandle>,
) {
  const reactId = useId()
  const listboxId = `${reactId}-listbox`
  const labelId = `${reactId}-label`
  const generatedTriggerId = triggerId ?? `${reactId}-trigger`

  const triggerRef = useRef<HTMLButtonElement>(null)
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

  // Filtered + ranked list. When the query is empty we return the original
  // option order so users get a stable A→Z view of every player on first open.
  const filtered = useMemo(() => {
    const q = query.trim()
    if (!q) return options
    return options
      .map((o) => ({ option: o, score: scoreMatch(o, q) }))
      .filter((entry) => entry.score > 0)
      .sort((a, b) => b.score - a.score)
      .map((entry) => entry.option)
  }, [options, query])

  // Ref mirror of `filtered` so the open-effect can read the latest list
  // without having to subscribe to it (which would cause focus thrash).
  const filteredRef = useRef(filtered)
  useLayoutEffect(() => {
    filteredRef.current = filtered
  }, [filtered])

  const closePopover = useCallback(
    (returnFocus = true) => {
      setOpen(false)
      if (returnFocus) {
        // Defer so React commits the close before we move focus back; this
        // avoids the focus-trap warning when the input is removed mid-blur.
        requestAnimationFrame(() => triggerRef.current?.focus())
      }
    },
    [],
  )

  const openPopover = useCallback(() => {
    if (disabled) return
    setQuery('')
    setOpen(true)
  }, [disabled])

  // Imperative handle for parent components (e.g. Cmd-K shortcut).
  useImperativeHandle(
    ref,
    () => ({
      focus: () => triggerRef.current?.focus(),
      open: openPopover,
      close: () => closePopover(true),
    }),
    [openPopover, closePopover],
  )

  // When the popover OPENS (not on every keystroke), jump the highlight to
  // the currently-selected option and move keyboard focus into the search
  // input. `useLayoutEffect` lets the highlight land before paint so the
  // listbox doesn't briefly flash with a different active row. We deliberately
  // depend on `open` only — re-running on `selectedOption`/`filtered` would
  // steal focus from the user mid-typing.
  useLayoutEffect(() => {
    if (!open) return
    const list = filteredRef.current
    const sel = selectedOption
    const idx = sel ? list.findIndex((o) => o.value === sel.value) : -1
    setHighlight(idx >= 0 ? idx : 0)
    const id = requestAnimationFrame(() => inputRef.current?.focus())
    return () => cancelAnimationFrame(id)
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [open])

  // Keep highlight in range as the filtered list shrinks/grows during typing.
  useEffect(() => {
    if (!open) return
    if (filtered.length === 0) {
      setHighlight(0)
      return
    }
    if (highlight >= filtered.length) setHighlight(filtered.length - 1)
  }, [filtered.length, highlight, open])

  // Scroll the active option into view as the user navigates.
  useEffect(() => {
    if (!open) return
    const node = optionRefs.current[highlight]
    if (node) node.scrollIntoView({ block: 'nearest' })
  }, [open, highlight])

  // Click-outside dismissal — uses pointerdown so we beat the option's click.
  // The option commits on pointerdown too (with preventDefault) so we never
  // race into "close before commit".
  useEffect(() => {
    if (!open) return
    const onDocPointerDown = (e: PointerEvent) => {
      if (!containerRef.current) return
      if (!containerRef.current.contains(e.target as Node)) {
        closePopover(false)
      }
    }
    document.addEventListener('pointerdown', onDocPointerDown)
    return () => document.removeEventListener('pointerdown', onDocPointerDown)
  }, [open, closePopover])

  const commit = (idx: number) => {
    const opt = filtered[idx]
    if (!opt) return
    onChange(opt.value, opt)
    closePopover(true)
  }

  const handleListKeyDown = (e: KeyboardEvent<HTMLInputElement>) => {
    if (disabled) return
    switch (e.key) {
      case 'ArrowDown':
        e.preventDefault()
        setHighlight((h) => (filtered.length === 0 ? 0 : (h + 1) % filtered.length))
        return
      case 'ArrowUp':
        e.preventDefault()
        setHighlight((h) =>
          filtered.length === 0 ? 0 : (h - 1 + filtered.length) % filtered.length,
        )
        return
      case 'Home':
        e.preventDefault()
        setHighlight(0)
        return
      case 'End':
        e.preventDefault()
        setHighlight(Math.max(0, filtered.length - 1))
        return
      case 'Enter':
        e.preventDefault()
        commit(highlight)
        return
      case 'Escape':
        e.preventDefault()
        closePopover(true)
        return
      case 'Tab':
        // Allow native focus traversal but close so the popover doesn't linger.
        closePopover(false)
        return
      default:
        return
    }
  }

  const handleTriggerKeyDown = (e: KeyboardEvent<HTMLButtonElement>) => {
    if (disabled) return
    if (e.key === 'ArrowDown' || e.key === 'Enter' || e.key === ' ') {
      e.preventDefault()
      openPopover()
    }
  }

  const activeOptionId = open && filtered[highlight] ? `${listboxId}-opt-${highlight}` : undefined

  return (
    <div ref={containerRef} className={cn('relative', className)}>
      <span id={labelId} className="sr-only">
        {ariaLabel}
      </span>

      <button
        ref={triggerRef}
        id={generatedTriggerId}
        type="button"
        role="combobox"
        aria-haspopup="listbox"
        aria-expanded={open}
        aria-controls={open ? listboxId : undefined}
        aria-labelledby={labelId}
        aria-activedescendant={activeOptionId}
        disabled={disabled}
        onClick={() => (open ? closePopover(false) : openPopover())}
        onKeyDown={handleTriggerKeyDown}
        className={cn(
          'group w-full flex items-center gap-3 text-left rounded-lg border transition-colors',
          'bg-surface border-border-default hover:border-primary-500/60',
          'dark:bg-surface-2 dark:border-border-default dark:hover:border-primary-500/60',
          'focus:outline-none disabled:cursor-not-allowed disabled:opacity-60',
          renderTrigger ? 'p-2' : 'px-3 py-2',
        )}
      >
        {renderTrigger ? (
          <span className="flex-1 min-w-0">{renderTrigger(selectedOption)}</span>
        ) : (
          <span
            className={cn(
              'flex-1 min-w-0 truncate text-sm font-mono',
              selectedOption ? 'text-text-primary' : 'text-text-muted',
            )}
          >
            {selectedOption ? selectedOption.label : triggerPlaceholder}
          </span>
        )}
        <ChevronUpDown />
      </button>

      {description && (
        <p className="mt-1 text-xs text-text-muted font-mono">{description}</p>
      )}

      {open && (
        <>
          {/*
            Mobile sheet backdrop — dims the page behind the bottom sheet.
            Hidden on `sm:` and up where the popover renders inline.
          */}
          <div
            aria-hidden="true"
            className="sm:hidden fixed inset-0 bg-black/50 z-40"
            onClick={() => closePopover(false)}
          />

          <div
            className={cn(
              // Mobile: full-width bottom sheet anchored to the viewport.
              'fixed inset-x-0 bottom-0 z-50 max-h-[85vh] rounded-t-2xl shadow-2xl',
              // Desktop: anchored popover under the trigger.
              'sm:absolute sm:bottom-auto sm:top-full sm:inset-x-auto sm:left-0 sm:right-0 sm:mt-2 sm:max-h-[420px] sm:rounded-lg',
              'flex flex-col overflow-hidden',
              'bg-surface dark:bg-surface-2 border border-border-subtle ring-1 ring-black/5',
            )}
          >
            <div className="flex items-center gap-2 border-b border-border-subtle p-3">
              <SearchIcon />
              <input
                ref={inputRef}
                type="text"
                role="searchbox"
                autoComplete="off"
                spellCheck={false}
                aria-autocomplete="list"
                aria-controls={listboxId}
                aria-activedescendant={activeOptionId}
                placeholder={searchPlaceholder}
                value={query}
                onChange={(e) => {
                  setQuery(e.target.value)
                  setHighlight(0)
                }}
                onKeyDown={handleListKeyDown}
                className={cn(
                  'flex-1 bg-transparent text-sm text-text-primary font-mono',
                  'placeholder:text-text-muted focus:outline-none',
                )}
              />
              {query && (
                <button
                  type="button"
                  aria-label="Clear search"
                  onClick={() => {
                    setQuery('')
                    setHighlight(0)
                    inputRef.current?.focus()
                  }}
                  className="text-text-muted hover:text-text-primary text-xs px-1"
                >
                  ✕
                </button>
              )}
            </div>

            <ul
              id={listboxId}
              role="listbox"
              aria-labelledby={labelId}
              className="flex-1 overflow-y-auto py-1"
            >
              {filtered.length === 0 ? (
                <li
                  role="option"
                  aria-selected="false"
                  aria-disabled="true"
                  className="px-3 py-3 text-sm text-text-muted font-mono"
                >
                  {emptyMessage
                    ? emptyMessage(query)
                    : query
                      ? `No matches for "${query}"`
                      : 'No options'}
                </li>
              ) : (
                filtered.map((opt, idx) => {
                  const isActive = idx === highlight
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
                      onPointerDown={(e) => {
                        // pointerdown so we commit before the document
                        // dismiss handler can close us. preventDefault keeps
                        // focus on the input until commit() returns it.
                        e.preventDefault()
                        commit(idx)
                      }}
                      onMouseEnter={() => setHighlight(idx)}
                      // ≥44px touch target on mobile via min-h-[44px].
                      className={cn(
                        'min-h-[44px] px-3 py-2 cursor-pointer flex items-center gap-3 text-sm',
                        isActive
                          ? 'bg-primary-50 dark:bg-primary-500/10'
                          : 'hover:bg-surface-2 dark:hover:bg-surface-3',
                      )}
                    >
                      {renderOption ? (
                        renderOption(opt, { query, isActive, isSelected })
                      ) : (
                        <span className="flex-1 flex items-center justify-between gap-3">
                          <span className="truncate text-text-primary font-mono">{opt.label}</span>
                          {opt.hint && (
                            <span className="shrink-0 text-xs text-text-muted font-mono">
                              {opt.hint}
                            </span>
                          )}
                        </span>
                      )}
                      {isSelected && <CheckIcon />}
                    </li>
                  )
                })
              )}
            </ul>
          </div>
        </>
      )}
    </div>
  )
}

/**
 * Forwarded-ref wrapper. We can't simply `forwardRef(ComboboxInner)` because
 * generics get erased; this preserves the `<T>` parameter for callers.
 */
const Combobox = forwardRef(ComboboxInner) as <T>(
  props: ComboboxProps<T> & { ref?: React.Ref<ComboboxHandle> },
) => ReturnType<typeof ComboboxInner>

export default Combobox

// ---------------------------------------------------------------------------
// Local icons — small inline SVGs to avoid adding an icon dependency just for
// the combobox affordances.

function ChevronUpDown() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.5}
      className="shrink-0 h-4 w-4 text-text-muted group-hover:text-text-secondary"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M7 8l3-3 3 3M7 12l3 3 3-3" />
    </svg>
  )
}

function SearchIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={1.75}
      className="shrink-0 h-4 w-4 text-text-muted"
    >
      <circle cx="9" cy="9" r="6" />
      <path strokeLinecap="round" d="M14 14l3 3" />
    </svg>
  )
}

function CheckIcon() {
  return (
    <svg
      aria-hidden="true"
      viewBox="0 0 20 20"
      fill="none"
      stroke="currentColor"
      strokeWidth={2}
      className="shrink-0 h-4 w-4 text-primary-600 dark:text-primary-400"
    >
      <path strokeLinecap="round" strokeLinejoin="round" d="M5 10l3 3 7-7" />
    </svg>
  )
}
