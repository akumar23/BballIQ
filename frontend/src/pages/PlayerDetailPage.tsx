import { useParams } from 'react-router-dom'
import { usePlayer } from '@/hooks/usePlayers'
import MetricGauge from '@/components/MetricGauge'
import { formatMetric } from '@/lib/utils'

export default function PlayerDetailPage() {
  const { id } = useParams<{ id: string }>()
  const { data: player, isLoading, error } = usePlayer(Number(id))

  if (isLoading) {
    return <div className="text-center py-8">Loading player...</div>
  }

  if (error || !player) {
    return <div className="text-center py-8 text-red-500">Player not found</div>
  }

  return (
    <div className="max-w-4xl mx-auto">
      <div className="bg-white rounded-lg shadow-sm border border-gray-200 p-6">
        <div className="flex justify-between items-start mb-6">
          <div>
            <h1 className="text-3xl font-bold text-gray-900">{player.name}</h1>
            <p className="text-gray-500 dark:text-white">
              {player.position} • {player.team_abbreviation} • {player.season}
            </p>
            {player.games_played && (
              <p className="text-sm text-gray-400">{player.games_played} games played</p>
            )}
          </div>
        </div>

        {player.metrics && (
          <div className="grid grid-cols-3 gap-4 mb-8">
            <MetricGauge
              label="OFFENSE"
              value={player.metrics.offensive_metric}
              percentile={player.metrics.offensive_percentile}
              color="offense"
            />
            <MetricGauge
              label="DEFENSE"
              value={player.metrics.defensive_metric}
              percentile={player.metrics.defensive_percentile}
              color="defense"
            />
            <div className="rounded-lg p-3 bg-gray-100">
              <span className="text-xs font-medium text-gray-600">OVERALL</span>
              <p className="text-2xl font-bold text-gray-900">
                {formatMetric(player.metrics.overall_metric)}
              </p>
            </div>
          </div>
        )}

        {player.tracking_stats && (
          <div>
            <h2 className="text-lg font-semibold text-gray-900 mb-4">Tracking Stats</h2>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <StatBox label="Total Touches" value={player.tracking_stats.touches} />
              <StatBox label="Points/Touch" value={player.tracking_stats.points_per_touch} decimal />
              <StatBox label="Deflections" value={player.tracking_stats.deflections} />
              <StatBox label="Contested Shots" value={player.tracking_stats.contested_shots} />
            </div>
          </div>
        )}
      </div>
    </div>
  )
}

function StatBox({ label, value, decimal = false }: { label: string; value: number | null; decimal?: boolean }) {
  return (
    <div className="bg-gray-50 rounded-lg p-3">
      <p className="text-xs text-gray-500">{label}</p>
      <p className="text-xl font-semibold text-gray-900">
        {value === null ? '-' : decimal ? value.toFixed(3) : value}
      </p>
    </div>
  )
}
