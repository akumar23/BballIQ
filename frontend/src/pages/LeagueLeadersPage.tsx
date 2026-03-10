import { usePerGameLeaderboard } from '@/hooks/usePlayers'
import type { PlayerPerGameStats } from '@/types'

const STAT_SECTIONS = [
  { key: 'ppg', label: 'Points Per Game' },
  { key: 'rpg', label: 'Rebounds Per Game' },
  { key: 'apg', label: 'Assists Per Game' },
  { key: 'mpg', label: 'Minutes Per Game' },
  { key: 'spg', label: 'Steals Per Game' },
  { key: 'bpg', label: 'Blocks Per Game' },
]

function StatSection({ statKey, label }: { statKey: string; label: string }) {
  const { data, isLoading, error } = usePerGameLeaderboard(statKey)

  return (
    <div className="bg-white rounded-lg p-4 border border-gray-200">
      <h2 className="text-lg font-semibold text-gray-900 mb-3">{label}</h2>
      {isLoading ? (
        <p className="text-gray-500 text-sm">Loading...</p>
      ) : error ? (
        <p className="text-red-500 text-sm">Error loading stats</p>
      ) : (
        <ol className="space-y-2">
          {data?.map((player: PlayerPerGameStats, i: number) => (
            <li key={player.id} className="flex justify-between items-center text-sm">
              <span className="text-gray-400 w-5">{i + 1}</span>
              <span className="flex-1 text-gray-900">{player.name}</span>
              <span className="text-gray-400 text-xs mr-2">{player.team_abbreviation}</span>
              <span className="text-yellow-500 font-bold">
                {player[statKey as keyof PlayerPerGameStats]}
              </span>
            </li>
          ))}
        </ol>
      )}
    </div>
  )
}

export default function LeagueLeadersPage() {
  return (
    <div className="p-6 max-w-6xl mx-auto">
      <h1 className="text-3xl font-bold text-gray-900 mb-6">League Leaders</h1>
      <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
        {STAT_SECTIONS.map(({ key, label }) => (
          <StatSection key={key} statKey={key} label={label} />
        ))}
      </div>
    </div>
  )
}
