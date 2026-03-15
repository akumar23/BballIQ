import { useState, useEffect } from 'react'
import { cortexPlayers } from '@/data/cortexMockData'
import type { CortexPlayer } from '@/data/cortexMockData'
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

export default function PlayerCardPage() {
  const [selectedPlayer, setSelectedPlayer] = useState<CortexPlayer>(cortexPlayers[0])
  const [activeTab, setActiveTab] = useState<TabName>('Overview')
  const [animKey, setAnimKey] = useState(0)

  useEffect(() => {
    setAnimKey((k) => k + 1)
  }, [selectedPlayer, activeTab])

  const renderTab = () => {
    switch (activeTab) {
      case 'Overview':
        return <OverviewTab player={selectedPlayer} />
      case 'Offense':
        return <OffenseTab player={selectedPlayer} />
      case 'Defense':
        return <DefenseTab player={selectedPlayer} />
      case 'Impact':
        return <ImpactTab player={selectedPlayer} />
      case 'Portability':
        return <PortabilityTab player={selectedPlayer} />
      case 'Championship':
        return <ChampionshipTab player={selectedPlayer} />
      case 'Trajectory':
        return <TrajectoryTab player={selectedPlayer} />
    }
  }

  return (
    <div>
      {/* Player Selector */}
      <div className="flex gap-2 overflow-x-auto pb-4 scrollbar-hide">
        {cortexPlayers.map((p) => (
          <button
            key={p.id}
            onClick={() => setSelectedPlayer(p)}
            className={`px-4 py-2 rounded text-sm font-mono whitespace-nowrap transition-all ${
              selectedPlayer.id === p.id
                ? 'bg-primary-600 text-white'
                : 'bg-white border border-gray-200 text-gray-500 hover:text-gray-900 hover:border-gray-300'
            }`}
          >
            {p.name.split(' ').pop()}
          </button>
        ))}
      </div>

      {/* Player Header */}
      <div className="flex items-center gap-5 mb-6">
        <div className="w-14 h-14 rounded border-2 border-primary-600 flex items-center justify-center">
          <span className="text-primary-600 font-mono font-bold text-lg">
            {selectedPlayer.number}
          </span>
        </div>
        <div className="flex-1">
          <h2 className="text-3xl font-bold text-gray-900">{selectedPlayer.name}</h2>
          <p className="text-gray-500 text-sm">
            {selectedPlayer.team} · {selectedPlayer.position} · Age {selectedPlayer.age} ·{' '}
            <span className="font-mono">{selectedPlayer.mpg}</span> MPG
          </p>
        </div>
        <div className="flex gap-3">
          {[
            { label: 'EPM', value: selectedPlayer.impact.epm },
            { label: 'WS/48', value: selectedPlayer.advanced.ws48 },
            { label: 'TS%', value: selectedPlayer.advanced.ts },
          ].map((s) => (
            <div
              key={s.label}
              className="bg-gray-50 border border-gray-200 rounded px-4 py-2 text-center min-w-[80px]"
            >
              <p className="text-[10px] text-gray-500 uppercase tracking-wider">{s.label}</p>
              <p className="text-xl font-mono font-bold text-gray-900">
                {typeof s.value === 'number'
                  ? s.label === 'TS%'
                    ? (s.value * 100).toFixed(1)
                    : s.value.toFixed(1)
                  : s.value}
              </p>
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
    </div>
  )
}
