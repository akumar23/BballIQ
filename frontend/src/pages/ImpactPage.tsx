import { useState } from 'react'
import { Link } from 'react-router-dom'
import { useImpactLeaderboard } from '@/hooks/useImpact'
import { cn, formatMetric, getPercentileColor } from '@/lib/utils'
import type { ImpactLeaderboardEntry } from '@/types'

type SortType = 'net' | 'offense' | 'defense'

function ImpactBar({ value, max = 10 }: { value: number | null; max?: number }) {
  if (value === null) return <div className="w-full h-2 bg-gray-100 rounded" />

  const percentage = Math.min(Math.abs(value) / max * 100, 100)
  const isPositive = value >= 0

  return (
    <div className="w-full h-2 bg-gray-100 rounded overflow-hidden relative">
      <div
        className={cn(
          'absolute top-0 h-full rounded',
          isPositive ? 'bg-green-500 left-1/2' : 'bg-red-500 right-1/2'
        )}
        style={{ width: `${percentage / 2}%` }}
      />
      <div className="absolute top-0 left-1/2 w-px h-full bg-gray-300" />
    </div>
  )
}

function ImpactBadge({ value, label }: { value: number | null; label: string }) {
  if (value === null) return null

  const isPositive = value >= 0
  return (
    <span
      className={cn(
        'inline-flex items-center px-2 py-0.5 rounded text-xs font-medium',
        isPositive ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
      )}
    >
      {label}: {isPositive ? '+' : ''}{formatMetric(value)}
    </span>
  )
}

function PlayerImpactRow({ player, rank }: { player: ImpactLeaderboardEntry; rank: number }) {
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
      <td className="px-4 py-3">
        <div className="flex flex-col gap-1">
          <div className="flex items-center gap-2">
            <span className={cn(
              'text-lg font-bold',
              (player.contextualized_net_impact ?? 0) >= 0 ? 'text-green-600' : 'text-red-600'
            )}>
              {(player.contextualized_net_impact ?? 0) >= 0 ? '+' : ''}
              {formatMetric(player.contextualized_net_impact)}
            </span>
            <span className={cn('text-sm', getPercentileColor(player.impact_percentile))}>
              {player.impact_percentile}th
            </span>
          </div>
          <ImpactBar value={player.contextualized_net_impact} />
        </div>
      </td>
      <td className="px-4 py-3 text-center">
        <span className={cn(
          'font-medium',
          (player.contextualized_off_impact ?? 0) >= 0 ? 'text-amber-600' : 'text-red-500'
        )}>
          {(player.contextualized_off_impact ?? 0) >= 0 ? '+' : ''}
          {formatMetric(player.contextualized_off_impact)}
        </span>
      </td>
      <td className="px-4 py-3 text-center">
        <span className={cn(
          'font-medium',
          (player.contextualized_def_impact ?? 0) <= 0 ? 'text-blue-600' : 'text-red-500'
        )}>
          {(player.contextualized_def_impact ?? 0) >= 0 ? '+' : ''}
          {formatMetric(player.contextualized_def_impact)}
        </span>
      </td>
      <td className="px-4 py-3">
        <div className="flex flex-col gap-1">
          <span className="text-sm text-gray-600">
            Raw: {(player.raw_net_rating_diff ?? 0) >= 0 ? '+' : ''}{formatMetric(player.raw_net_rating_diff)}
          </span>
          <span className="text-sm text-gray-500">
            Teammate Adj: {(player.teammate_adjustment ?? 0) >= 0 ? '+' : ''}{formatMetric(player.teammate_adjustment)}
          </span>
        </div>
      </td>
      <td className="px-4 py-3 text-center">
        <div className="flex flex-col items-center">
          <span className="text-sm font-medium text-gray-700">
            {((player.reliability_factor ?? 0) * 100).toFixed(0)}%
          </span>
          <div className="w-12 h-1 bg-gray-200 rounded mt-1">
            <div
              className="h-full bg-primary-500 rounded"
              style={{ width: `${(player.reliability_factor ?? 0) * 100}%` }}
            />
          </div>
        </div>
      </td>
    </tr>
  )
}

export default function ImpactPage() {
  const [sortBy, setSortBy] = useState<SortType>('net')
  const { data: players, isLoading, error } = useImpactLeaderboard(sortBy)

  const tabs: { key: SortType; label: string; description: string }[] = [
    { key: 'net', label: 'Net Impact', description: 'Overall on/off adjusted for context' },
    { key: 'offense', label: 'Offensive', description: 'Offensive impact adjusted' },
    { key: 'defense', label: 'Defensive', description: 'Defensive impact adjusted' },
  ]

  return (
    <div>
      <div className="mb-6">
        <h1 className="text-2xl font-bold text-gray-900">Contextualized Impact</h1>
        <p className="text-gray-600 mt-1">
          On/Off ratings adjusted for teammate quality, opponent strength, and sample size
        </p>
      </div>

      {/* Explanation Card */}
      <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
        <h3 className="font-medium text-blue-900 mb-2">How it works</h3>
        <ul className="text-sm text-blue-800 space-y-1">
          <li>• <strong>Raw On/Off</strong>: Team net rating when player is on court vs off</li>
          <li>• <strong>Teammate Adjustment</strong>: Accounts for playing with strong/weak teammates</li>
          <li>• <strong>Opponent Quality</strong>: Weights impact vs starters higher than vs bench</li>
          <li>• <strong>Reliability</strong>: More minutes = more confident in the rating</li>
        </ul>
      </div>

      {/* Sort Tabs */}
      <div className="flex gap-2 mb-6">
        {tabs.map(tab => (
          <button
            key={tab.key}
            onClick={() => setSortBy(tab.key)}
            className={cn(
              'px-4 py-2 rounded-lg font-medium transition-colors',
              sortBy === tab.key
                ? 'bg-primary-600 text-white'
                : 'bg-gray-100 text-gray-600 hover:bg-gray-200'
            )}
            title={tab.description}
          >
            {tab.label}
          </button>
        ))}
      </div>

      {isLoading && (
        <div className="text-center py-8">
          <div className="inline-block animate-spin rounded-full h-8 w-8 border-4 border-primary-500 border-t-transparent" />
          <p className="mt-2 text-gray-600">Loading impact data...</p>
        </div>
      )}

      {error && (
        <div className="text-center py-8">
          <p className="text-red-500">Error loading impact data</p>
          <p className="text-sm text-gray-500 mt-1">
            Make sure to run the impact data fetch script first
          </p>
        </div>
      )}

      {players && players.length > 0 && (
        <div className="overflow-x-auto">
          <table className="min-w-full divide-y divide-gray-200">
            <thead className="bg-gray-50">
              <tr>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Rank
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Player
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Net Impact
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Off Impact
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Def Impact
                </th>
                <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Adjustments
                </th>
                <th className="px-4 py-3 text-center text-xs font-medium text-gray-500 uppercase tracking-wider">
                  Reliability
                </th>
              </tr>
            </thead>
            <tbody className="bg-white divide-y divide-gray-200">
              {players.map((player, index) => (
                <PlayerImpactRow key={player.id} player={player} rank={index + 1} />
              ))}
            </tbody>
          </table>
        </div>
      )}

      {players && players.length === 0 && (
        <div className="text-center py-8 bg-gray-50 rounded-lg">
          <p className="text-gray-600">No impact data available</p>
          <p className="text-sm text-gray-500 mt-1">
            Run <code className="bg-gray-200 px-1 rounded">python -m scripts.fetch_impact_data</code> to populate
          </p>
        </div>
      )}
    </div>
  )
}
