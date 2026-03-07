import { formatMetric, getPercentileColor } from '@/lib/utils'
import { cn } from '@/lib/utils'

interface MetricGaugeProps {
  label: string
  value: number | null
  percentile: number | null
  color: 'offense' | 'defense'
}

export default function MetricGauge({ label, value, percentile, color }: MetricGaugeProps) {
  const bgColor = color === 'offense' ? 'bg-offense-light' : 'bg-defense-light'
  const textColor = color === 'offense' ? 'text-offense-dark' : 'text-defense-dark'

  return (
    <div className={cn('rounded-lg p-3', bgColor)}>
      <div className="flex justify-between items-center">
        <span className={cn('text-xs font-medium', textColor)}>{label}</span>
        {percentile !== null && (
          <span className={cn('text-xs', getPercentileColor(percentile))}>
            {percentile}th
          </span>
        )}
      </div>
      <p className={cn('text-2xl font-bold', textColor)}>
        {formatMetric(value)}
      </p>
    </div>
  )
}
