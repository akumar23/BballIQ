import { useEffect, useMemo, useState } from 'react'
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

export default function PlayerCardPage() {
  const [searchParams, setSearchParams] = useSearchParams()
  const [selectedValue, setSelectedValue] = useState<string>('')
  const [activeTab, setActiveTab] = useState<TabName>('Overview')
  const [animKey, setAnimKey] = useState(0)

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
    [cardApiData]
  )

  // Reset active tab whenever a new player card loads.
  useEffect(() => {
    if (cardApiData) {
      setActiveTab('Overview')
    }
  }, [cardApiData])

  useEffect(() => {
    setAnimKey((k) => k + 1)
  }, [cardData, activeTab])

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
        <select
          value={selectedValue}
          onChange={(e) => setSelectedValue(e.target.value)}
          className="w-full max-w-md px-3 py-2 bg-white border border-gray-200 rounded text-sm text-gray-900 font-mono focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 cursor-pointer"
          disabled={options.length === 0}
        >
          {options.length === 0 && (
            <option value="">
              {optionsLoading ? 'Loading players…' : optionsError ? 'Unable to load players' : 'No players available'}
            </option>
          )}
          {options.map((opt) => (
            <option
              key={encodeOption(opt.id, opt.season)}
              value={encodeOption(opt.id, opt.season)}
            >
              {opt.name} ({opt.season})
            </option>
          ))}
        </select>
        {options.length > 0 && (
          <p className="mt-1 text-xs text-gray-400 font-mono dark:text-white">{options.length} player seasons available</p>
        )}
        {optionsError && (
          <p className="mt-1 text-xs text-red-500 font-mono">
            Failed to load player list: {optionsErrorObj instanceof Error ? optionsErrorObj.message : 'Unknown error'}
          </p>
        )}
      </div>

      {cardLoading ? (
        <div className="flex items-center justify-center h-64">
          <p className="text-gray-400 font-mono text-sm animate-pulse">Loading player data…</p>
        </div>
      ) : cardError ? (
        <div className="flex flex-col items-center justify-center h-64 gap-3">
          <p className="text-red-500 font-mono text-sm">
            Failed to load player card: {cardErrorObj instanceof Error ? cardErrorObj.message : 'Unknown error'}
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
          {/* Player Header */}
          <div className="flex items-center gap-5 mb-6">
            <div className="w-14 h-14 rounded border-2 border-primary-600 flex items-center justify-center">
              <span className="text-primary-600 font-mono font-bold text-sm">
                {cardData.number ? `#${cardData.number}` : cardData.position}
              </span>
            </div>
            <div className="flex-1">
              <h2 className="text-3xl font-bold text-gray-900 dark:text-white">{cardData.name}</h2>
              <p className="text-gray-500 text-sm dark:text-white">
                {cardData.team} · {cardData.position}
                {cardData.age ? ` · ${Math.floor(cardData.age)} yrs` : ''}
                {' '}·{' '}
                <span className="font-mono">{cardData.mpg.toFixed(1)}</span> MPG ·{' '}
                <span className="font-mono text-primary-600">
                  {selectedValue ? decodeOption(selectedValue).season : ''}
                </span>
              </p>
            </div>
            <div className="flex gap-3">
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
                  className="bg-gray-50 border border-gray-200 rounded px-4 py-2 text-center min-w-[80px]"
                >
                  <p className="text-[10px] text-gray-500 uppercase tracking-wider">{s.label}</p>
                  <p className="text-xl font-mono font-bold text-gray-900">{s.format(s.value)}</p>
                </div>
              ))}
            </div>
          </div>

          {/* Tabs */}
          <div className="flex gap-1 border-b border-gray-200 mb-6">
            {TABS.map((tab) => (
              <button
                key={tab}
                onClick={() => setActiveTab(tab)}
                className={`px-4 py-2.5 text-xs uppercase tracking-[1.5px] transition-all rounded-t ${
                  activeTab === tab
                    ? 'bg-primary-600 text-white'
                    : 'text-gray-500 hover:text-gray-900 dark:text-gray-400 dark:hover:text-white'
                }`}
              >
                {tab}
              </button>
            ))}
          </div>

          {/* Tab Content */}
          <div key={animKey} className="animate-fadeUp">
            {renderTab()}
          </div>
        </>
      ) : null}
    </div>
  )
}
