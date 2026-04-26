import { useState } from 'react'
import { usePlayers } from '@/hooks/usePlayers'
import PlayerCard from '@/components/PlayerCard'
import { useSeason } from '@/context/SeasonContext'

export default function PlayersPage() {
  const [search, setSearch] = useState('')
  const { season } = useSeason()
  const { data: players, isLoading, error } = usePlayers({ season })

  const filteredPlayers = players?.filter(player =>
    player.name.toLowerCase().includes(search.toLowerCase())
  )

  if (isLoading) {
    return <div className="text-center py-8">Loading players...</div>
  }

  if (error) {
    return <div className="text-center py-8 text-red-500">Error loading players</div>
  }

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 mb-4 dark:text-white">Players</h1>
        <input
          type="text"
          placeholder="Search players..."
          value={search}
          onChange={(e) => setSearch(e.target.value)}
          className="w-full max-w-md px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-primary-500 focus:border-transparent"
        />
      </div>
      <div className="grid gap-4 md:grid-cols-2 lg:grid-cols-3">
        {filteredPlayers?.map(player => (
          <PlayerCard key={player.id} player={player} />
        ))}
      </div>
    </div>
  )
}
