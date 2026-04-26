import { useState } from 'react'
import { Link } from 'react-router-dom'
import { usePlayTypeLeaderboard } from '@/hooks/usePlayTypes'
import { cn } from '@/lib/utils'
import type { PlayTypeKey, PlayTypeSortBy, PlayTypeLeaderboardEntry } from '@/types/playType'
import { PLAY_TYPE_LABELS, SORT_BY_LABELS } from '@/types/playType'
import { useSeason } from '@/context/SeasonContext'

const PLAY_TYPE_TABS: { key: PlayTypeKey; label: string }[] = [
  { key: 'isolation', label: 'Isolation' },
  { key: 'pnr_ball_handler', label: 'PnR Handler' },
  { key: 'pnr_roll_man', label: 'PnR Roll' },
  { key: 'post_up', label: 'Post-Up' },
  { key: 'spot_up', label: 'Spot-Up' },
  { key: 'transition', label: 'Transition' },
  { key: 'cut', label: 'Cut' },
  { key: 'off_screen', label: 'Off Screen' },
]

const SORT_OPTIONS: { key: PlayTypeSortBy; label: string }[] = [
  { key: 'ppp', label: 'PPP' },
  { key: 'possessions', label: 'Possessions' },
  { key: 'fg_pct', label: 'FG%' },
  { key: 'frequency', label: 'Frequency' },
]

function formatPPP(value: number | null): string {
  if (value === null) return '—'
  return Number(value).toFixed(2)
}

function formatPercent(value: number | null): string {
  if (value === null) return '—'
  return `${(Number(value) * 100).toFixed(1)}%`
}

function PPPBadge({ ppp, percentile }: { ppp: number | null; percentile: number | null }) {
  if (ppp === null) return <span className="text-gray-400">—</span>

  const getColor = () => {
    if (percentile === null) return 'bg-gray-100 text-gray-700'
    if (percentile >= 80) return 'bg-green-100 text-green-800'
    if (percentile >= 60) return 'bg-green-50 text-green-700'
    if (percentile >= 40) return 'bg-gray-100 text-gray-700'
    if (percentile >= 20) return 'bg-orange-50 text-orange-700'
    return 'bg-red-100 text-red-800'
  }

  return (
    <span className={cn('inline-flex items-center px-2.5 py-0.5 rounded-full text-sm font-medium', getColor())}>
      {formatPPP(ppp)}
    </span>
  )
}

function PlayerRow({ entry, rank, sortBy }: { entry: PlayTypeLeaderboardEntry; rank: number; sortBy: PlayTypeSortBy }) {
  return (
    <tr className="hover:bg-gray-50 transition-colors">
      <td className="px-4 py-3 whitespace-nowrap">
        <span className="inline-flex items-center justify-center w-8 h-8 rounded-full bg-gray-100 text-gray-600 text-sm font-medium">
          {rank}
        </span>
      </td>
      <td className="px-4 py-3">
        <Link to={`/players/${entry.id}`} className="hover:text-primary-600">
          <div className="font-medium text-gray-900">{entry.name}</div>
          <div className="text-sm text-gray-500">
            {entry.position} • {entry.team_abbreviation}
          </div>
        </Link>
      </td>
      <td className={cn('px-4 py-3 text-center', sortBy === 'possessions' && 'bg-yellow-50')}>
        <span className={cn('text-sm', sortBy === 'possessions' ? 'font-bold text-yellow-700' : 'text-gray-600')}>
          {entry.possessions ?? '—'}
        </span>
      </td>
      <td className={cn('px-4 py-3 text-center', sortBy === 'ppp' && 'bg-yellow-50')}>
        <PPPBadge ppp={entry.ppp} percentile={entry.ppp_percentile} />
      </td>
      <td className={cn('px-4 py-3 text-center', sortBy === 'fg_pct' && 'bg-yellow-50')}>
        <span className={cn('text-sm', sortBy === 'fg_pct' ? 'font-bold text-yellow-700' : 'text-gray-600')}>
          {formatPercent(entry.fg_pct)}
        </span>
      </td>
      <td className={cn('px-4 py-3 text-center', sortBy === 'frequency' && 'bg-yellow-50')}>
        <span className={cn('text-sm', sortBy === 'frequency' ? 'font-bold text-yellow-700' : 'text-gray-600')}>
          {formatPercent(entry.frequency)}
        </span>
      </td>
      <td className="px-4 py-3 text-center">
        <span className="text-sm text-gray-600">{entry.points ?? '—'}</span>
      </td>
    </tr>
  )
}

export default function PlayTypesPage() {
  const [activePlayType, setActivePlayType] = useState<PlayTypeKey>('isolation')
  const [sortBy, setSortBy] = useState<PlayTypeSortBy>('ppp')
  const { season } = useSeason()
  const { data, isLoading, error } = usePlayTypeLeaderboard(activePlayType, sortBy, season, 50, 50)

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900 dark:text-white">Play Types</h1>
        <p className="text-gray-600 mt-1 dark:text-white">
          Offensive play type efficiency for the {season} season (min. 50 possessions)
        </p>
      </div>

      {/* Play Type Tabs */}
      <div className="mb-4">
        <div className="text-sm font-medium text-gray-500 mb-2 dark:text-white">Play Type</div>
        <div className="flex flex-wrap gap-2">
          {PLAY_TYPE_TABS.map(tab => (
            <button
              key={tab.key}
              onClick={() => setActivePlayType(tab.key)}
              className={cn(
                'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                activePlayType === tab.key
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              )}
            >
              {tab.label}
            </button>
          ))}
        </div>
      </div>

      {/* Sort Options */}
      <div className="mb-6">
        <div className="text-sm font-medium text-gray-500 mb-2 dark:text-white">Sort By</div>
        <div className="flex gap-2">
          {SORT_OPTIONS.map(option => (
            <button
              key={option.key}
              onClick={() => setSortBy(option.key)}
              className={cn(
                'px-3 py-1.5 rounded-lg text-sm font-medium transition-colors',
                sortBy === option.key
                  ? 'bg-gray-800 text-white'
                  : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
              )}
            >
              {option.label}
            </button>
          ))}
        </div>
      </div>

      {isLoading && (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent" />
          <p className="mt-2 text-gray-600">Loading...</p>
        </div>
      )}

      {error && (
        <div className="text-center py-8">
          <p className="text-red-500">Error loading play type stats</p>
        </div>
      )}

      {data && data.entries.length > 0 && (
        <div className="overflow-x-auto">
          <div className="mb-4 text-sm text-gray-600 dark:text-white">
            Showing <span className="font-medium">{PLAY_TYPE_LABELS[activePlayType]}</span> leaders
            sorted by <span className="font-medium">{SORT_BY_LABELS[sortBy]}</span>
          </div>
          <table className="min-w-full divide-y divide-gray-200 table-fixed">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-16">
                  Rank
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider w-48">
                  Player
                </th>
                <th className={cn(
                  'px-4 py-3 text-center text-xs font-medium uppercase tracking-wider',
                  sortBy === 'possessions' ? 'text-primary-600' : 'text-gray-500'
                )}>
                  POSS
                </th>
                <th className={cn(
                  'px-4 py-3 text-center text-xs font-medium uppercase tracking-wider',
                  sortBy === 'ppp' ? 'text-primary-600' : 'text-gray-500'
                )}>
                  PPP
                </th>
                <th className={cn(
                  'px-4 py-3 text-center text-xs font-medium uppercase tracking-wider',
                  sortBy === 'fg_pct' ? 'text-primary-600' : 'text-gray-500'
                )}>
                  FG%
                </th>
                <th className={cn(
                  'px-4 py-3 text-center text-xs font-medium uppercase tracking-wider',
                  sortBy === 'frequency' ? 'text-primary-600' : 'text-gray-500'
                )}>
                  FREQ
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  PTS
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {data.entries.map((entry, index) => (
                <PlayerRow key={entry.id} entry={entry} rank={index + 1} sortBy={sortBy} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {data && data.entries.length === 0 && (
        <div className="text-center py-8">
          <p className="text-gray-500">No data available for this play type</p>
        </div>
      )}

      {/* Info Card */}
      <div className="mt-8 bg-gray-50 rounded-lg p-4">
        <h3 className="font-medium text-gray-900 mb-2">About Play Type Stats</h3>
        <ul className="text-sm text-gray-600 space-y-1">
          <li><strong>PPP</strong> - Points per possession: Total points scored divided by possessions</li>
          <li><strong>FG%</strong> - Field goal percentage: Shots made divided by shots attempted</li>
          <li><strong>Frequency</strong> - How often this play type is used relative to all possessions</li>
          <li><strong>Minimum 50 possessions</strong> required for leaderboard eligibility</li>
        </ul>
      </div>
    </div>
  )
}
