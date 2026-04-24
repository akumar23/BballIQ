import { useState } from 'react'
import { useLeaderboard } from '@/hooks/usePlayers'
import PlayerCard from '@/components/PlayerCard'
import { cn } from '@/lib/utils'
import { useSeason } from '@/context/SeasonContext'

type LeaderboardType = 'offensive' | 'defensive' | 'overall'

export default function LeaderboardPage() {
  const [type, setType] = useState<LeaderboardType>('overall')
  const { season } = useSeason()
  const { data: players, isLoading, error } = useLeaderboard(type, season)

  const tabs: { key: LeaderboardType; label: string }[] = [
    { key: 'overall', label: 'Overall' },
    { key: 'offensive', label: 'Offense' },
    { key: 'defensive', label: 'Defense' },
  ]

  return (
    <div>
      <h1 className="text-2xl font-bold text-gray-900 mb-6">Leaderboard</h1>

      <div className="flex gap-2 mb-6">
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setType(tab.key)}
            className={cn(
              'px-4 py-2 rounded-lg font-medium transition-colors',
              type === tab.key
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading && <div className="text-center py-8">Loading leaderboard...</div>}
      {error && <div className="text-center py-8 text-red-500">Error loading leaderboard</div>}

      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {players?.map((player, index) => (
          <PlayerCard key={player.id} player={player} rank={index + 1} season={season} />
        ))}
      </div>
    </div>
  )
}
