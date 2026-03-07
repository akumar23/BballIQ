import { Link } from 'react-router-dom'
import type { Player } from '@/types'
import { formatMetric, getPercentileColor } from '@/lib/utils'
import MetricGauge from './MetricGauge'

interface PlayerCardProps {
  player: Player
  rank?: number
}

export default function PlayerCard({ player, rank }: PlayerCardProps) {
  return (
    <Link
      to={`/players/${player.id}`}
      className="block bg-white rounded-lg shadow-sm border border-gray-200 p-4 hover:shadow-md transition-shadow"
    >
      <div className="flex items-start gap-4">
        {rank && (
          <span className="text-2xl font-bold text-gray-300 w-8">
            {rank}
          </span>
        )}
        <div className="flex-1">
          <div className="flex justify-between items-start">
            <div>
              <h3 className="font-semibold text-gray-900">{player.name}</h3>
              <p className="text-sm text-gray-500">
                {player.position} • {player.team_abbreviation}
              </p>
            </div>
          </div>
          {player.metrics && (
            <div className="mt-3 grid grid-cols-2 gap-4">
              <MetricGauge
                label="OFF"
                value={player.metrics.offensive_metric}
                percentile={player.metrics.offensive_percentile}
                color="offense"
              />
              <MetricGauge
                label="DEF"
                value={player.metrics.defensive_metric}
                percentile={player.metrics.defensive_percentile}
                color="defense"
              />
            </div>
          )}
        </div>
      </div>
    </Link>
  )
}
