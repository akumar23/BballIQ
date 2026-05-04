import { useId, useState } from 'react'
import { useLeaderboard } from '@/hooks/usePlayers'
import PlayerCard from '@/components/PlayerCard'
import TabList, { type TabItem } from '@/components/ui/TabList'
import { useSeason } from '@/context/SeasonContext'

type LeaderboardType = 'offensive' | 'defensive' | 'overall'

export default function LeaderboardPage() {
  const [type, setType] = useState<LeaderboardType>('overall')
  const { season } = useSeason()
  const { data: players, isLoading, error } = useLeaderboard(type, season)
  const panelId = useId()

  const tabs: TabItem<LeaderboardType>[] = [
    { key: 'overall', label: 'Overall' },
    { key: 'offensive', label: 'Offense' },
    { key: 'defensive', label: 'Defense' },
  ]

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6 dark:text-white">Leaderboard</h1>

      <TabList<LeaderboardType>
        tabs={tabs}
        activeKey={type}
        onChange={setType}
        ariaLabel="Leaderboard type"
        panelId={panelId}
        className="mb-6"
      />

      {isLoading && (
        <div className="text-center py-8" role="status" aria-live="polite">
          Loading leaderboard...
        </div>
      )}
      {error && (
        <div className="text-center py-8 text-rose-600 dark:text-rose-400" role="alert">
          Error loading leaderboard
        </div>
      )}

      <div id={panelId} role="tabpanel" className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {players?.map((player, index) => (
          <PlayerCard key={player.id} player={player} rank={index + 1} season={season} />
        ))}
      </div>
    </div>
  )
}
