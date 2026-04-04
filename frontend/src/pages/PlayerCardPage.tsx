import { useState, useEffect } from 'react'
import type { CortexPlayer } from '@/data/cortexTypes'
import type { PlayerCardOption } from '@/types'
import { api } from '@/lib/api'
import { mapApiToPlayer } from '@/lib/playerMapper'
import OverviewTab from '@/components/cortex/OverviewTab'
import OffenseTab from '@/components/cortex/OffenseTab'
import DefenseTab from '@/components/cortex/DefenseTab'
import ImpactTab from '@/components/cortex/ImpactTab'
import PortabilityTab from '@/components/cortex/PortabilityTab'
import ChampionshipTab from '@/components/cortex/ChampionshipTab'
import TrajectoryTab from '@/components/cortex/TrajectoryTab'

const TABS = [
  'Overview',
  'Offense',
  'Defense',
  'Impact',
  'Portability',
  'Championship',
  'Trajectory',
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
  const [options, setOptions] = useState<PlayerCardOption[]>([])
  const [selectedValue, setSelectedValue] = useState<string>('')
  const [cardData, setCardData] = useState<CortexPlayer | null>(null)
  const [loading, setLoading] = useState(true)
  const [activeTab, setActiveTab] = useState<TabName>('Overview')
  const [animKey, setAnimKey] = useState(0)

  // Load all available player+season options on mount
  useEffect(() => {
    api.players.available().then((data) => {
      setOptions(data)
      if (data.length > 0) {
        const first = encodeOption(data[0].id, data[0].season)
        setSelectedValue(first)
      }
    })
  }, [])

  // Fetch card data whenever the selection changes
  useEffect(() => {
    if (!selectedValue) return
    const { id, season } = decodeOption(selectedValue)
    setLoading(true)
    api.players
      .card(id, season)
      .then((data) => {
        setCardData(mapApiToPlayer(data))
        setActiveTab('Overview')
      })
      .finally(() => setLoading(false))
  }, [selectedValue])

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
            <option value="">Loading players…</option>
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
          <p className="mt-1 text-xs text-gray-400 font-mono">{options.length} player seasons available</p>
        )}
      </div>

      {loading ? (
        <div className="flex items-center justify-center h-64">
          <p className="text-gray-400 font-mono text-sm animate-pulse">Loading player data…</p>
        </div>
      ) : cardData ? (
        <>
          {/* Player Header */}
          <div className="flex items-center gap-5 mb-6">
            <div className="w-14 h-14 rounded border-2 border-primary-600 flex items-center justify-center">
              <span className="text-primary-600 font-mono font-bold text-sm">
                {cardData.position}
              </span>
            </div>
            <div className="flex-1">
              <h2 className="text-3xl font-bold text-gray-900">{cardData.name}</h2>
              <p className="text-gray-500 text-sm">
                {cardData.team} · {cardData.position} ·{' '}
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
                    : 'text-gray-500 hover:text-gray-900'
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
