import { useEffect, useId, useMemo, useRef, useState } from 'react'
import type { KeyboardEvent } from 'react'
import { useSearchParams } from 'react-router-dom'
import { useQuery } from '@tanstack/react-query'
import type { CortexPlayer } from '@/data/cortexTypes'
import { api } from '@/lib/api'
import { mapApiToPlayer } from '@/lib/playerMapper'
import OverviewTab from '@/components/cortex/OverviewTab'
import OffenseTab from '@/components/cortex/OffenseTab'
import DefenseTab from '@/components/cortex/DefenseTab'
import ImpactTab from '@/components/cortex/ImpactTab'
import PortabilityTab from '@/components/cortex/PortabilityTab'
import ChampionshipTab from '@/components/cortex/ChampionshipTab'
import TrajectoryTab from '@/components/cortex/TrajectoryTab'
import GameLogsTab from '@/components/cortex/GameLogsTab'
import Combobox, { type ComboboxOption } from '@/components/ui/Combobox'
import Stat from '@/components/ui/Stat'
import type { PlayerCardOption } from '@/types'

const TABS = [
  'Overview',
  'Offense',
  'Defense',
  'Impact',
  'Portability',
  'Championship',
  'Trajectory',
  'Game Log',
] as const

type TabName = (typeof TABS)[number]

/** Encode a player+season as a single dropdown value string. */
const encodeOption = (id: number, season: string) => `${id}|${season}`

/** Decode a dropdown value string back into player id and season. */
const decodeOption = (value: string): { id: number; season: string } => {
  const [id, season] = value.split('|')
  return { id: Number(id), season }
}

/**
 * Initial of the player's first + last name. Used as the headshot fallback
 * monogram so we always have a recognizable avatar even when CDN 404s.
 */
function getMonogram(name: string | undefined | null): string {
  if (!name) return '?'
  const parts = name.trim().split(/\s+/)
  const first = parts[0]?.[0] ?? ''
  const last = parts.length > 1 ? parts[parts.length - 1][0] : ''
  return `${first}${last}`.toUpperCase() || '?'
}

export default function PlayerCardPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedValue, setSelectedValue] = useState<string>('')
  const [activeTab, setActiveTab] = useState<TabName>('Overview')
  // Per-mount fade key — bumps when the tab changes so the panel content fades
  // in over 150ms without re-mounting on every data change.
  const [fadeKey, setFadeKey] = useState(0)
  const [headshotFailed, setHeadshotFailed] = useState(false)

  const tabIdBase = useId()
  const tabRefs = useRef<Record<string, HTMLButtonElement | null>>({})

  // Load all available player+season options on mount.
  const {
    data: options = [],
    isLoading: optionsLoading,
    isError: optionsError,
    error: optionsErrorObj,
  } = useQuery({
    queryKey: ['players', 'available'],
    queryFn: () => api.players.available(),
  })

  // Pre-select from URL params (?playerId=X&season=Y) if present, otherwise
  // fall back to the first option.
  useEffect(() => {
    if (selectedValue || options.length === 0) return
    const urlPlayerId = searchParams.get('playerId')
    const urlSeason = searchParams.get('season')
    if (urlPlayerId) {
      const match = options.find(
        (o) => o.id === Number(urlPlayerId) && (!urlSeason || o.season === urlSeason),
      )
      if (match) {
        setSelectedValue(encodeOption(match.id, match.season))
        return
      }
    }
    setSelectedValue(encodeOption(options[0].id, options[0].season))
  }, [options, selectedValue, searchParams])

  // Keep the URL in sync with the dropdown so the card is shareable/linkable.
  useEffect(() => {
    if (!selectedValue) return
    const { id, season } = decodeOption(selectedValue)
    const urlPlayerId = searchParams.get('playerId')
    const urlSeason = searchParams.get('season')
    if (urlPlayerId === String(id) && urlSeason === season) return
    setSearchParams({ playerId: String(id), season }, { replace: true })
  }, [selectedValue, searchParams, setSearchParams])

  // Decode selection for the card query. React Query keys the request on
  // (id, season) so stale responses for prior selections are discarded
  // automatically — eliminates the race condition the old effect had.
  const decoded = selectedValue ? decodeOption(selectedValue) : null
  const playerId = decoded?.id
  const season = decoded?.season

  const {
    data: cardApiData,
    isLoading: cardLoading,
    isError: cardError,
    error: cardErrorObj,
    refetch: refetchCard,
  } = useQuery({
    queryKey: ['player-card', playerId, season],
    queryFn: () => api.players.card(playerId as number, season),
    enabled: !!playerId && !!season,
  })

  // Derive CortexPlayer inline rather than holding shadow state.
  const cardData: CortexPlayer | null = useMemo(
    () => (cardApiData ? mapApiToPlayer(cardApiData) : null),
    [cardApiData],
  )

  // Reset active tab + headshot whenever a new player card loads.
  useEffect(() => {
    if (cardApiData) {
      setActiveTab('Overview')
      setHeadshotFailed(false)
    }
  }, [cardApiData])

  // Bump the fade key only on tab change — content does a 150ms opacity fade
  // without a full remount or translate.
  useEffect(() => {
    setFadeKey((k) => k + 1)
  }, [activeTab])

  // Build combobox options once per options/PlayerCardOption[] change.
  const comboboxOptions = useMemo<ComboboxOption<PlayerCardOption>[]>(
    () =>
      options.map((opt) => {
        const team = opt.team_abbreviation ?? ''
        const teamSegment = team ? `${team} ` : ''
        return {
          value: encodeOption(opt.id, opt.season),
          label: `${opt.name} — ${teamSegment}(${opt.season})`,
          hint: opt.position ?? undefined,
          data: opt,
        }
      }),
    [options],
  )

  // Tab-strip keyboard handling: ArrowLeft/ArrowRight wrap, Home/End jump.
  const handleTabKeyDown = (e: KeyboardEvent<HTMLDivElement>) => {
    const idx = TABS.indexOf(activeTab)
    if (idx < 0) return
    let nextIdx: number | null = null
    if (e.key === 'ArrowRight') nextIdx = (idx + 1) % TABS.length
    else if (e.key === 'ArrowLeft') nextIdx = (idx - 1 + TABS.length) % TABS.length
    else if (e.key === 'Home') nextIdx = 0
    else if (e.key === 'End') nextIdx = TABS.length - 1
    if (nextIdx === null) return
    e.preventDefault()
    const next = TABS[nextIdx]
    setActiveTab(next)
    tabRefs.current[next]?.focus()
  }

  const tabId = (tab: TabName) => `${tabIdBase}-tab-${tab.replace(/\s+/g, '-')}`
  const panelId = (tab: TabName) => `${tabIdBase}-panel-${tab.replace(/\s+/g, '-')}`

  const renderTab = () => {
    if (!cardData) return null
    switch (activeTab) {
      case 'Overview':
        return <OverviewTab player={cardData} />
      case 'Offense':
        return <OffenseTab player={cardData} />
      case 'Defense':
        return <DefenseTab player={cardData} />
      case 'Impact':
        return <ImpactTab player={cardData} />
      case 'Portability':
        return <PortabilityTab player={cardData} />
      case 'Championship':
        return <ChampionshipTab player={cardData} />
      case 'Trajectory':
        return <TrajectoryTab player={cardData} />
      case 'Game Log':
        return <GameLogsTab player={cardData} />
    }
  }

  return (
    <div>
      {/* Player + Season Selector */}
      <div className="mb-6">
        <Combobox<PlayerCardOption>
          options={comboboxOptions}
          value={selectedValue}
          onChange={(v) => setSelectedValue(v)}
          ariaLabel="Select a player and season"
          placeholder={
            optionsLoading
              ? 'Loading players…'
              : optionsError
                ? 'Unable to load players'
                : 'Search players…'
          }
          disabled={comboboxOptions.length === 0}
          className="max-w-md"
          description={
            comboboxOptions.length > 0
              ? `${comboboxOptions.length} player seasons available`
              : undefined
          }
          emptyMessage="No matching players"
        />
        {optionsError && (
          <p
            role="alert"
            className="mt-1 text-xs text-rose-600 dark:text-rose-400 font-mono"
          >
            Failed to load player list:{' '}
            {optionsErrorObj instanceof Error ? optionsErrorObj.message : 'Unknown error'}
          </p>
        )}
      </div>

      {cardLoading ? (
        <div
          className="flex items-center justify-center h-64"
          role="status"
          aria-live="polite"
        >
          <p className="text-gray-500 dark:text-gray-400 font-mono text-sm animate-pulse">
            Loading player data…
          </p>
        </div>
      ) : cardError ? (
        <div
          className="flex flex-col items-center justify-center h-64 gap-3"
          role="alert"
        >
          <p className="text-rose-600 dark:text-rose-400 font-mono text-sm">
            Failed to load player card:{' '}
            {cardErrorObj instanceof Error ? cardErrorObj.message : 'Unknown error'}
          </p>
          <button
            type="button"
            onClick={() => refetchCard()}
            className="px-4 py-2 text-xs uppercase tracking-[1.5px] bg-primary-600 text-white rounded hover:bg-primary-700 transition-colors"
          >
            Retry
          </button>
        </div>
      ) : cardData ? (
        <>
          {/*
            Sticky identity header — pinned under the global nav (h-16 = 64px)
            with backdrop blur so long tab content scrolls behind it. The
            sticky context allows users to keep the player's KPIs visible
            while exploring deep tab tables.
          */}
          <div
            className="sticky top-16 z-20 -mx-4 px-4 sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8 mb-6 backdrop-blur bg-white/80 dark:bg-gray-950/80 border-b border-gray-200 dark:border-gray-800"
          >
            <div className="flex items-center gap-5 py-4">
              {!headshotFailed ? (
                <img
                  src={`https://cdn.nba.com/headshots/nba/latest/1040x760/${cardData.id}.png`}
                  alt={cardData.name}
                  loading="lazy"
                  onError={() => setHeadshotFailed(true)}
                  className="w-14 h-14 rounded object-cover bg-primary-50 dark:bg-primary-500/10 border border-gray-200 dark:border-gray-700"
                />
              ) : (
                <div
                  className="w-14 h-14 rounded bg-primary-500/10 dark:bg-primary-500/20 border border-primary-500/30 flex items-center justify-center"
                  aria-hidden="true"
                >
                  <span className="text-primary-700 dark:text-primary-300 font-mono font-bold text-base">
                    {getMonogram(cardData.name)}
                  </span>
                </div>
              )}
              <div className="flex-1 min-w-0">
                <h2 className="text-2xl sm:text-3xl font-bold text-gray-900 dark:text-white truncate">
                  {cardData.name}
                </h2>
                <p className="text-gray-500 dark:text-gray-300 text-sm">
                  {cardData.team} · {cardData.position}
                  {cardData.age ? ` · ${Math.floor(cardData.age)} yrs` : ''}{' '}·{' '}
                  <span className="font-mono">{cardData.mpg.toFixed(1)}</span> MPG ·{' '}
                  <span className="font-mono text-primary-600 dark:text-primary-400">
                    {selectedValue ? decodeOption(selectedValue).season : ''}
                  </span>
                </p>
              </div>
              <div className="hidden sm:flex gap-3">
                {[
                  {
                    label: 'NET RTG',
                    value: cardData.impact.contextualized.contextualizedNetRtg,
                    format: (v: number) => (v > 0 ? `+${v.toFixed(1)}` : v.toFixed(1)),
                  },
                  {
                    label: 'WS/48',
                    value: cardData.advanced.ws48,
                    format: (v: number) => v.toFixed(3),
                  },
                  {
                    label: 'TS%',
                    value: cardData.advanced.ts,
                    format: (v: number) => `${(v * 100).toFixed(1)}`,
                  },
                ].map((s) => (
                  <div
                    key={s.label}
                    className="bg-surface-3 border border-border-subtle rounded px-4 py-2 min-w-[80px]"
                  >
                    <Stat label={s.label} value={s.format(s.value)} size="md" align="center" />
                  </div>
                ))}
              </div>
            </div>
          </div>

          {/*
            Tab strip — real WAI-ARIA tab pattern with roving tabindex,
            arrow-key navigation, snap-x mobile scroll, and an overflow hint
            gradient on the right edge.
          */}
          <div className="relative mb-6">
            <div
              role="tablist"
              aria-label="Player analytics sections"
              onKeyDown={handleTabKeyDown}
              className="flex gap-1 overflow-x-auto snap-x snap-mandatory border-b border-gray-200 dark:border-gray-700 scroll-smooth"
            >
              {TABS.map((tab) => {
                const isActive = activeTab === tab
                return (
                  <button
                    key={tab}
                    id={tabId(tab)}
                    ref={(el) => {
                      tabRefs.current[tab] = el
                    }}
                    role="tab"
                    type="button"
                    aria-selected={isActive}
                    aria-controls={panelId(tab)}
                    tabIndex={isActive ? 0 : -1}
                    onClick={() => setActiveTab(tab)}
                    className={`shrink-0 snap-start px-4 py-2.5 text-xs uppercase tracking-[1.5px] transition-all rounded-t border-b-2 ${
                      isActive
                        ? 'bg-primary-600 text-white border-primary-600 dark:bg-primary-700'
                        : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white border-transparent'
                    }`}
                  >
                    {tab}
                  </button>
                )
              })}
            </div>
            {/* Right-edge overflow hint — only renders on small screens. */}
            <div
              aria-hidden="true"
              className="md:hidden pointer-events-none absolute top-0 right-0 h-full w-8 bg-gradient-to-l from-white dark:from-gray-950 to-transparent"
            />
          </div>

          {/* Tab Content — opacity fade only, keyed on tab change. */}
          <div
            key={fadeKey}
            id={panelId(activeTab)}
            role="tabpanel"
            aria-labelledby={tabId(activeTab)}
            className="animate-tab-fade"
          >
            {renderTab()}
          </div>
        </>
      ) : null}
    </div>
  )
}
