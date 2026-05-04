import { useEffect, useId, useState } from 'react'
import { Link } from 'react-router-dom'
import { usePerGameLeaderboard, useLeaderboardSeasons } from '@/hooks/usePlayers'
import { useSeason } from '@/context/SeasonContext'
import { cn } from '@/lib/utils'
import TabList, { type TabItem } from '@/components/ui/TabList'
import DataTable from '@/components/ui/DataTable'
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

const TAB_ITEMS: TabItem<StatKey>[] = TABS.map((t) => ({ key: t.key, label: t.label }))

function StatCell({ value, highlight }: { value: number | null; highlight: boolean }) {
  return (
    <td className="px-4 py-3 text-center">
      <span
        className={cn(
          'text-sm',
          highlight
            ? 'text-lg font-bold text-amber-600 dark:text-amber-400'
            : 'text-gray-600 dark:text-gray-300',
        )}
      >
        {value ?? '—'}
      </span>
    </td>
  )
}

function PlayerRow({
  player,
  rank,
  statKey,
}: {
  player: PlayerPerGameStats
  rank: number
  statKey: StatKey
}) {
  return (
    <tr className="hover:bg-gray-50 dark:hover:bg-gray-800 transition-colors">
      <td className="px-4 py-3 whitespace-nowrap">
        <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-300 text-sm font-medium">
          {rank}
        </span>
      </td>
      <td className="px-4 py-3">
        <Link to={`/players/${player.id}`} className="hover:text-primary-600">
          <div className="font-medium text-gray-900 dark:text-white">{player.name}</div>
          <div className="text-sm text-gray-500 dark:text-gray-400">
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
  const seasonSelectId = useId()
  const panelId = useId()

  useEffect(() => {
    setSelectedSeason(globalSeason)
  }, [globalSeason])
  const { data: players, isLoading, error } = usePerGameLeaderboard(activeTab, selectedSeason, 50)

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">League Leaders</h1>
        <p className="text-gray-600 mt-1 dark:text-white">
          Per game stats for the {selectedSeason} season
        </p>
      </div>

      <div className="flex flex-col sm:flex-row gap-2 mb-6 items-start">
        <div className="flex flex-col">
          <label htmlFor={seasonSelectId} className="sr-only">
            Season
          </label>
          <select
            id={seasonSelectId}
            value={selectedSeason}
            onChange={(e) => setSelectedSeason(e.target.value)}
            className="px-3 py-2 rounded-lg bg-gray-100 dark:bg-gray-700 text-gray-600 dark:text-gray-200 font-medium"
          >
            {seasons?.map((s) => (
              <option key={s.season} value={s.season}>
                {s.season}
              </option>
            ))}
          </select>
        </div>
        <TabList<StatKey>
          tabs={TAB_ITEMS}
          activeKey={activeTab}
          onChange={setActiveTab}
          ariaLabel="Per-game stat category"
          panelId={panelId}
        />
      </div>

      {isLoading && (
        <div className="text-center py-8" role="status" aria-live="polite">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent" />
          <p className="mt-2 text-gray-600 dark:text-gray-300">Loading...</p>
        </div>
      )}

      {error && (
        <div className="text-center py-8" role="alert">
          <p className="text-rose-600 dark:text-rose-400">Error loading stats</p>
        </div>
      )}

      {players && players.length > 0 && (
        <div id={panelId} role="tabpanel">
          <DataTable
            caption={`League leaders for ${selectedSeason} season, sorted by ${
              TABS.find((t) => t.key === activeTab)?.label
            }`}
          >
            <thead>
              <tr>
                <th
                  scope="col"
                  className="px-4 py-3 text-left text-caption font-medium text-text-muted uppercase tracking-wider w-16"
                >
                  Rank
                </th>
                <th
                  scope="col"
                  className="px-4 py-3 text-left text-caption font-medium text-text-muted uppercase tracking-wider w-48"
                >
                  Player
                </th>
                {TABS.map((tab) => (
                  <th
                    key={tab.key}
                    scope="col"
                    className={cn(
                      'px-4 py-3 text-center text-caption font-medium uppercase tracking-wider',
                      activeTab === tab.key
                        ? 'text-primary-600 dark:text-primary-400'
                        : 'text-text-muted',
                    )}
                  >
                    {tab.header}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {players.map((player, index) => (
                <PlayerRow key={player.id} player={player} rank={index + 1} statKey={activeTab} />
              ))}
            </tbody>
          </DataTable>
        </div>
      )}
    </div>
  )
}
