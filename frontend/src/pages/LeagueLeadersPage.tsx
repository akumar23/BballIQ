import { useState, useEffect } from 'react'
import { Link } from 'react-router-dom'
import { usePerGameLeaderboard, useLeaderboardSeasons } from '@/hooks/usePlayers'
import { useSeason } from '@/context/SeasonContext'
import { cn } from '@/lib/utils'
import type { PlayerPerGameStats } from '@/types'
type StatKey = 'games_played' | 'ppg' | 'rpg' | 'apg' | 'mpg' | 'spg' | 'bpg'

const TABS: { key: StatKey; label: string; header: string }[] = [
  { key: 'games_played', label: 'Games Played', header: 'GP' },
  { key: 'ppg', label: 'Points', header: 'PPG' },
  { key: 'rpg', label: 'Rebounds', header: 'RPG' },
  { key: 'apg', label: 'Assists', header: 'APG' },
  { key: 'mpg', label: 'Minutes', header: 'MPG' },
  { key: 'spg', label: 'Steals', header: 'SPG' },
  { key: 'bpg', label: 'Blocks', header: 'BPG' },
]

function StatCell({ value, highlight }: { value: number | null; highlight: boolean }) {
  return (
    <td className="px-4 py-3 text-center">
      <span className={cn('text-sm', highlight ? 'text-lg font-bold text-yellow-500' : 'text-gray-600')}>
        {value ?? '—'}
      </span>
    </td>
  )
}

function PlayerRow({ player, rank, statKey }: { player: PlayerPerGameStats; rank: number; statKey: StatKey }) {
  return (
    <tr className="hover:bg-gray-50 transition-colors">
      <td className="px-4 py-3 whitespace-nowrap">
        <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-gray-100 text-gray-600 text-sm font-medium">
          {rank}
        </span>
      </td>
      <td className="px-4 py-3">
        <Link to={`/players/${player.id}`} className="hover:text-primary-600">
          <div className="font-medium text-gray-900">{player.name}</div>
          <div className="text-sm text-gray-500">
            {player.position} • {player.team_abbreviation}
          </div>
        </Link>
      </td>
      <StatCell value={player.games_played} highlight={statKey === 'games_played'} />
      <StatCell value={player.ppg} highlight={statKey === 'ppg'} />
      <StatCell value={player.rpg} highlight={statKey === 'rpg'} />
      <StatCell value={player.apg} highlight={statKey === 'apg'} />
      <StatCell value={player.mpg} highlight={statKey === 'mpg'} />
      <StatCell value={player.spg} highlight={statKey === 'spg'} />
      <StatCell value={player.bpg} highlight={statKey === 'bpg'} />
    </tr>
  )
}

export default function LeagueLeadersPage() {
  const [activeTab, setActiveTab] = useState<StatKey>('ppg')
  const { season: globalSeason } = useSeason()
  const [selectedSeason, setSelectedSeason] = useState<string>(globalSeason)
  const { data: seasons } = useLeaderboardSeasons()

  useEffect(() => {
    setSelectedSeason(globalSeason)
  }, [globalSeason])
  const { data: players, isLoading, error } = usePerGameLeaderboard(activeTab, selectedSeason, 50)

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">League Leaders</h1>
        <p className="text-gray-600 mt-1 dark:text-white">Per game stats for the {selectedSeason} season</p>
      </div>
 
      <div className="flex gap-2 mb-6">
        <select
          value={selectedSeason}
          onChange={e => setSelectedSeason(e.target.value)}
          className="px-3 py-2 rounded-lg bg-gray-100 text-gray-600 font-medium"
        >
          {seasons?.map(s => (
            <option key={s.season} value={s.season}>{s.season}</option>
          ))}
        </select>
        {TABS.map(tab => (
          <button
            key={tab.key}
            onClick={() => setActiveTab(tab.key)}
            className={cn(
              'px-4 py-2 rounded-lg font-medium transition-colors',
              activeTab === tab.key
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent" />
          <p className="mt-2 text-gray-600">Loading...</p>
        </div>
      )}

      {error && (
        <div className="text-center py-8">
          <p className="text-red-500">Error loading stats</p>
        </div>
      )}

      {players && players.length > 0 && (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200 table-fixed">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-16">Rank</th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-48">Player</th>
                {TABS.map(tab => (
                  <th key={tab.key} className={cn(
                    'px-4 py-3 text-center text-xs font-medium uppercase tracking-wider',
                    activeTab === tab.key ? 'text-primary-600' : 'text-gray-500'
                  )}>
                    {tab.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {players.map((player, index) => (
                <PlayerRow key={player.id} player={player} rank={index + 1} statKey={activeTab} />
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  )
}
