import { useState, useMemo } from 'react'
import { useQuery } from '@tanstack/react-query'
import type { CortexPlayer } from '@/data/cortexTypes'
import type { GameLog } from '@/types'
import { api } from '@/lib/api'
import { SectionHeader } from './shared'

type SortField =
  | 'game_date'
  | 'minutes'
  | 'points'
  | 'rebounds'
  | 'assists'
  | 'steals'
  | 'blocks'
  | 'turnovers'
  | 'fg_pct'
  | 'fg3_pct'
  | 'ft_pct'
  | 'plus_minus'
  | 'game_score'

type SortDirection = 'asc' | 'desc'
type WLFilter = 'all' | 'W' | 'L'

function formatDate(dateStr: string | null): string {
  if (!dateStr) return '--'
  const date = new Date(dateStr)
  return date.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' })
}

function safeNum(val: number | null): number {
  return val ?? 0
}

function formatPct(val: number | null): string {
  if (val === null || val === undefined) return '--'
  return (val * 100).toFixed(1)
}

function SortArrow({ field, sortField, sortDir }: { field: SortField; sortField: SortField; sortDir: SortDirection }) {
  if (field !== sortField) {
    return <span className="ml-1 text-gray-300">&#8597;</span>
  }
  return <span className="ml-1 text-primary-600">{sortDir === 'asc' ? '\u2191' : '\u2193'}</span>
}

export default function GameLogsTab({ player }: { player: CortexPlayer }) {
  const [sortField, setSortField] = useState<SortField>('game_date')
  const [sortDir, setSortDir] = useState<SortDirection>('desc')
  const [wlFilter, setWLFilter] = useState<WLFilter>('all')
  const [searchQuery, setSearchQuery] = useState('')

  const { data: gameLogs, isLoading, isError } = useQuery({
    queryKey: ['gameLogs', player.id],
    queryFn: () => api.players.gameLogs(Number(player.id)),
    enabled: !!player.id,
  })

  const handleSort = (field: SortField) => {
    if (sortField === field) {
      setSortDir((prev) => (prev === 'asc' ? 'desc' : 'asc'))
    } else {
      setSortField(field)
      setSortDir(field === 'game_date' ? 'desc' : 'desc')
    }
  }

  const filteredAndSorted = useMemo(() => {
    if (!gameLogs) return []

    let filtered = [...gameLogs]

    // W/L filter
    if (wlFilter !== 'all') {
      filtered = filtered.filter((g) => g.wl === wlFilter)
    }

    // Search filter
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase()
      filtered = filtered.filter((g) => g.matchup?.toLowerCase().includes(q))
    }

    // Sort
    filtered.sort((a, b) => {
      let aVal: number | string = 0
      let bVal: number | string = 0

      if (sortField === 'game_date') {
        aVal = a.game_date ?? ''
        bVal = b.game_date ?? ''
        return sortDir === 'asc'
          ? aVal.localeCompare(bVal as string)
          : (bVal as string).localeCompare(aVal as string)
      }

      aVal = safeNum(a[sortField])
      bVal = safeNum(b[sortField])
      return sortDir === 'asc' ? aVal - bVal : bVal - aVal
    })

    return filtered
  }, [gameLogs, wlFilter, searchQuery, sortField, sortDir])

  const seasonAverages = useMemo(() => {
    if (!filteredAndSorted.length) return null

    const count = filteredAndSorted.length
    const sum = (key: keyof GameLog) =>
      filteredAndSorted.reduce((acc, g) => acc + safeNum(g[key] as number | null), 0)

    const totalFgm = sum('fgm')
    const totalFga = sum('fga')
    const totalFg3m = sum('fg3m')
    const totalFg3a = sum('fg3a')
    const totalFtm = sum('ftm')
    const totalFta = sum('fta')

    return {
      games: count,
      minutes: sum('minutes') / count,
      points: sum('points') / count,
      rebounds: sum('rebounds') / count,
      assists: sum('assists') / count,
      steals: sum('steals') / count,
      blocks: sum('blocks') / count,
      turnovers: sum('turnovers') / count,
      fgm: totalFgm / count,
      fga: totalFga / count,
      fg_pct: totalFga > 0 ? totalFgm / totalFga : 0,
      fg3m: totalFg3m / count,
      fg3a: totalFg3a / count,
      fg3_pct: totalFg3a > 0 ? totalFg3m / totalFg3a : 0,
      ftm: totalFtm / count,
      fta: totalFta / count,
      ft_pct: totalFta > 0 ? totalFtm / totalFta : 0,
      plus_minus: sum('plus_minus') / count,
      game_score: sum('game_score') / count,
    }
  }, [filteredAndSorted])

  const headerClass = 'px-4 py-3 cursor-pointer select-none whitespace-nowrap hover:text-gray-700 transition-colors'

  if (isLoading) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-gray-400 font-mono text-sm animate-pulse">Loading game logs...</p>
      </div>
    )
  }

  if (isError) {
    return (
      <div className="flex items-center justify-center h-64">
        <p className="text-red-500 font-mono text-sm">Failed to load game logs. Please try again.</p>
      </div>
    )
  }

  return (
    <div>
      <SectionHeader title="Game Log" tag={`${filteredAndSorted.length} GAMES`} />

      {/* Filters */}
      <div className="flex flex-col sm:flex-row items-start sm:items-center gap-3 mb-4">
        {/* W/L Filter */}
        <div className="flex gap-1">
          {(['all', 'W', 'L'] as const).map((filter) => (
            <button
              key={filter}
              onClick={() => setWLFilter(filter)}
              className={`px-3 py-1.5 text-xs uppercase tracking-wider rounded transition-colors ${
                wlFilter === filter
                  ? 'bg-primary-600 text-white'
                  : 'bg-gray-100 text-gray-500 hover:bg-gray-200'
              }`}
            >
              {filter === 'all' ? 'All' : filter === 'W' ? 'Wins' : 'Losses'}
            </button>
          ))}
        </div>

        {/* Search */}
        <input
          type="text"
          placeholder="Search matchup..."
          value={searchQuery}
          onChange={(e) => setSearchQuery(e.target.value)}
          className="px-3 py-1.5 text-sm bg-white border border-gray-200 rounded focus:outline-none focus:ring-2 focus:ring-primary-500 focus:border-primary-500 w-full sm:w-48 font-mono"
        />
      </div>

      {/* Table */}
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 overflow-hidden">
        <div className="overflow-x-auto">
          <table className="w-full text-sm">
            <thead>
              <tr className="border-b border-gray-200 text-[10px] text-gray-500 uppercase tracking-wider">
                <th className={`text-left ${headerClass}`} onClick={() => handleSort('game_date')}>
                  Date<SortArrow field="game_date" sortField={sortField} sortDir={sortDir} />
                </th>
                <th className={`text-left ${headerClass}`}>Matchup</th>
                <th className={`text-right ${headerClass}`} onClick={() => handleSort('minutes')}>
                  MIN<SortArrow field="minutes" sortField={sortField} sortDir={sortDir} />
                </th>
                <th className={`text-right ${headerClass}`} onClick={() => handleSort('points')}>
                  PTS<SortArrow field="points" sortField={sortField} sortDir={sortDir} />
                </th>
                <th className={`text-right ${headerClass}`} onClick={() => handleSort('rebounds')}>
                  REB<SortArrow field="rebounds" sortField={sortField} sortDir={sortDir} />
                </th>
                <th className={`text-right ${headerClass}`} onClick={() => handleSort('assists')}>
                  AST<SortArrow field="assists" sortField={sortField} sortDir={sortDir} />
                </th>
                <th className={`text-right ${headerClass}`} onClick={() => handleSort('steals')}>
                  STL<SortArrow field="steals" sortField={sortField} sortDir={sortDir} />
                </th>
                <th className={`text-right ${headerClass}`} onClick={() => handleSort('blocks')}>
                  BLK<SortArrow field="blocks" sortField={sortField} sortDir={sortDir} />
                </th>
                <th className={`text-right ${headerClass}`} onClick={() => handleSort('turnovers')}>
                  TOV<SortArrow field="turnovers" sortField={sortField} sortDir={sortDir} />
                </th>
                <th className={`text-right ${headerClass}`} onClick={() => handleSort('fg_pct')}>
                  FG<SortArrow field="fg_pct" sortField={sortField} sortDir={sortDir} />
                </th>
                <th className={`text-right ${headerClass}`} onClick={() => handleSort('fg3_pct')}>
                  3PT<SortArrow field="fg3_pct" sortField={sortField} sortDir={sortDir} />
                </th>
                <th className={`text-right ${headerClass}`} onClick={() => handleSort('ft_pct')}>
                  FT<SortArrow field="ft_pct" sortField={sortField} sortDir={sortDir} />
                </th>
                <th className={`text-right ${headerClass}`} onClick={() => handleSort('plus_minus')}>
                  +/-<SortArrow field="plus_minus" sortField={sortField} sortDir={sortDir} />
                </th>
                <th className={`text-right ${headerClass}`} onClick={() => handleSort('game_score')}>
                  GmSc<SortArrow field="game_score" sortField={sortField} sortDir={sortDir} />
                </th>
              </tr>
            </thead>
            <tbody>
              {/* Season Averages Row */}
              {seasonAverages && (
                <tr className="border-b border-gray-200 bg-gray-50 font-semibold">
                  <td className="px-4 py-2.5 text-gray-900 text-xs uppercase tracking-wider">Averages</td>
                  <td className="px-4 py-2.5 text-gray-500 font-mono text-xs">{seasonAverages.games} GP</td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-900">{seasonAverages.minutes.toFixed(1)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-900">{seasonAverages.points.toFixed(1)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-900">{seasonAverages.rebounds.toFixed(1)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-900">{seasonAverages.assists.toFixed(1)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-900">{seasonAverages.steals.toFixed(1)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-900">{seasonAverages.blocks.toFixed(1)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-900">{seasonAverages.turnovers.toFixed(1)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-900">
                    <span>{seasonAverages.fgm.toFixed(1)}/{seasonAverages.fga.toFixed(1)}</span>
                    <span className="block text-[10px] text-gray-500">{(seasonAverages.fg_pct * 100).toFixed(1)}%</span>
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-900">
                    <span>{seasonAverages.fg3m.toFixed(1)}/{seasonAverages.fg3a.toFixed(1)}</span>
                    <span className="block text-[10px] text-gray-500">{(seasonAverages.fg3_pct * 100).toFixed(1)}%</span>
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-900">
                    <span>{seasonAverages.ftm.toFixed(1)}/{seasonAverages.fta.toFixed(1)}</span>
                    <span className="block text-[10px] text-gray-500">{(seasonAverages.ft_pct * 100).toFixed(1)}%</span>
                  </td>
                  <td className={`px-4 py-2.5 text-right font-mono font-bold ${seasonAverages.plus_minus >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {seasonAverages.plus_minus >= 0 ? '+' : ''}{seasonAverages.plus_minus.toFixed(1)}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-900">{seasonAverages.game_score.toFixed(1)}</td>
                </tr>
              )}

              {/* Game Rows */}
              {filteredAndSorted.map((game, idx) => (
                <tr key={`${game.game_date}-${idx}`} className="border-b border-gray-100 hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-2.5 text-gray-900 whitespace-nowrap text-xs">{formatDate(game.game_date)}</td>
                  <td className="px-4 py-2.5 whitespace-nowrap">
                    <span className={`inline-block w-5 text-center font-mono font-bold text-xs mr-1.5 ${game.wl === 'W' ? 'text-green-600' : 'text-red-600'}`}>
                      {game.wl ?? '--'}
                    </span>
                    <span className="text-gray-700 text-xs">{game.matchup ?? '--'}</span>
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-700">{safeNum(game.minutes)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-700 font-bold">{safeNum(game.points)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-700">{safeNum(game.rebounds)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-700">{safeNum(game.assists)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-700">{safeNum(game.steals)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-700">{safeNum(game.blocks)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-700">{safeNum(game.turnovers)}</td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-700">
                    <span>{safeNum(game.fgm)}/{safeNum(game.fga)}</span>
                    <span className="block text-[10px] text-gray-500">{formatPct(game.fg_pct)}%</span>
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-700">
                    <span>{safeNum(game.fg3m)}/{safeNum(game.fg3a)}</span>
                    <span className="block text-[10px] text-gray-500">{formatPct(game.fg3_pct)}%</span>
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-700">
                    <span>{safeNum(game.ftm)}/{safeNum(game.fta)}</span>
                    <span className="block text-[10px] text-gray-500">{formatPct(game.ft_pct)}%</span>
                  </td>
                  <td className={`px-4 py-2.5 text-right font-mono font-bold ${safeNum(game.plus_minus) >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                    {safeNum(game.plus_minus) >= 0 ? '+' : ''}{safeNum(game.plus_minus)}
                  </td>
                  <td className="px-4 py-2.5 text-right font-mono text-gray-700">{game.game_score?.toFixed(1) ?? '--'}</td>
                </tr>
              ))}

              {filteredAndSorted.length === 0 && (
                <tr>
                  <td colSpan={14} className="px-4 py-8 text-center text-gray-400 font-mono text-sm">
                    No games found matching your filters.
                  </td>
                </tr>
              )}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  )
}
